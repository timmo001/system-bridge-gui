// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::error::Error;

use tauri::{
    menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem},
    tray::{ClickType, TrayIconBuilder},
    Manager,
};
use tauri::{App, AppHandle};
use tauri::{WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_autostart::MacosLauncher;
use tauri_plugin_autostart::ManagerExt;
// use tauri_plugin_updater::UpdaterExt;
use tokio;

// TODO: Add a way to close the backend server when the app is closed
// TODO: Restart the backend server if it's not running

#[derive(serde::Deserialize)]
struct APIBaseResponse {
    version: String,
}

#[derive(serde::Deserialize)]
struct Settings {
    api: SettingsAPI,
    autostart: bool,
    // log_level: String,
}

#[derive(serde::Deserialize)]
struct SettingsAPI {
    token: String,
    port: i32,
}

const BACKEND_HOST: &str = "127.0.0.1";

const WINDOW_WIDTH: f64 = 1280.0;
const WINDOW_HEIGHT: f64 = 720.0;

fn page_title_map() -> Vec<(&'static str, &'static str)> {
    vec![("data", "Data"), ("settings", "Settings")]
}

fn get_settings() -> Result<Settings, Box<dyn std::error::Error>> {
    // Get install directory from &localappdata%\timmo001\systembridge
    let install_path: String = format!(
        "{}/timmo001/systembridge",
        std::env::var("LOCALAPPDATA").unwrap()
    );

    // Read settings from {install_path}\settings.json
    let settings_path: String = format!("{}/settings.json", install_path);
    if !std::path::Path::new(&settings_path).exists() {
        return Err("Settings file not found".into());
    }

    let settings: String = std::fs::read_to_string(settings_path)?;
    let settings: Settings = serde_json::from_str(&settings)?;

    Ok(settings)
}

fn setup_autostart(app: &mut App, autostart: bool) -> Result<(), Box<dyn std::error::Error>> {
    println!("Autostart: {}", autostart);

    // Get the autostart manager
    let autostart_manager: tauri::State<'_, tauri_plugin_autostart::AutoLaunchManager> =
        app.autolaunch();

    if autostart {
        let _ = autostart_manager.enable();
    } else {
        let _ = autostart_manager.disable();
    }

    Ok(())
}

async fn check_backend(
    install_path: String,
    base_url: String,
) -> Result<(), Box<dyn std::error::Error>> {
    // Check if the backend server is running
    let response: reqwest::Response = reqwest::get(format!("{}/", base_url)).await?;

    if response.status().is_success() {
        println!("Backend server is already running");
    } else {
        println!("Backend server is not running, starting it...");
        let backend_path: String = format!("{}/backend/systembridge", install_path);
        let process: Result<std::process::Child, std::io::Error> =
            std::process::Command::new(backend_path).spawn();
        if process.is_err() {
            return Err("Failed to start the backend server".into());
        }

        println!("Backend server started");
        // Wait for the backend server to start
        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;

        // Check if the backend server is running
        let response: reqwest::Response = reqwest::get(format!("{}/", base_url)).await?;
        if !response.status().is_success() {
            return Err("Failed to start the backend server".into());
        }

        println!("Backend server is running");
    }

    Ok(())
}

async fn check_backend_api(
    base_url: String,
    token: String,
) -> Result<(), Box<dyn std::error::Error>> {
    // Check if the backend server is running
    let response: reqwest::Response =
        reqwest::get(format!("{}/api?token={}", base_url, token)).await?;

    if !response.status().is_success() {
        let response_code = response.status().as_u16();
        // Return error with the response code
        return Err(format!("Backend server returned an error: {}", response_code).into());
    }

    let response: APIBaseResponse = response.json().await?;
    println!("Backend server version: {}", response.version);

    Ok(())
}

fn create_window(app: &AppHandle, page: String) -> Result<(), Box<dyn std::error::Error>> {
    println!("Creating window: {}", page);

    let settings: Settings = get_settings().unwrap();

    let title: String = format!(
        "{} | System Bridge",
        page_title_map()
            .iter()
            .find(|(key, _)| key == &page)
            .unwrap()
            .1
    );

    let url: tauri::Url = format!(
        "http://{}:{}/app/{}.html?apiPort={}&token={}",
        BACKEND_HOST,
        settings.api.port.to_string().clone(),
        page,
        settings.api.port.clone(),
        settings.api.token.clone()
    )
    .parse()
    .unwrap();

    let window = app.get_webview_window("main");
    if window.is_some() {
        let mut window: tauri::WebviewWindow = window.unwrap();
        window.show().unwrap();
        window.navigate(url);
        window.set_title(title.as_str()).unwrap();
        window.set_focus().unwrap();
        return Ok(());
    }

    WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
        .inner_size(WINDOW_WIDTH, WINDOW_HEIGHT)
        .title(title)
        .build()
        .unwrap();

    Ok(())
}

#[tokio::main]
async fn main() {
    // Get install directory from &localappdata%\timmo001\systembridge
    let install_path: String = format!(
        "{}/timmo001/systembridge",
        std::env::var("LOCALAPPDATA").unwrap()
    );

    // Read settings from {install_path}\settings.json
    let settings_path: String = format!("{}/settings.json", install_path);
    if !std::path::Path::new(&settings_path).exists() {
        println!("Settings file not found");
        std::process::exit(1);
    }

    // Get settings
    let settings: Settings = get_settings().unwrap();

    let base_url: String = format!(
        "http://{}:{}",
        BACKEND_HOST,
        settings.api.port.to_string().clone()
    );

    // Check if the backend server is running
    let backend_active: Result<(), Box<dyn Error>> =
        check_backend(install_path.clone(), base_url.clone()).await;
    if !backend_active.is_ok() {
        println!("Backend is not running");
        std::process::exit(1);
    }

    // Check the backend API
    let api_active: Result<(), Box<dyn Error>> =
        check_backend_api(base_url.clone(), settings.api.token.clone()).await;
    if !api_active.is_ok() {
        println!("Backend API is not running");
        std::process::exit(1);
    }

    // Create the main window
    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_shell::init())
        // .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(move |app: &mut App| {
            // Check for updates
            // let handle: &tauri::AppHandle = app.handle();
            // tauri::async_runtime::spawn(async move {
            //     let response: Result<
            //         Option<tauri_plugin_updater::Update>,
            //         tauri_plugin_updater::Error,
            //     > = handle.updater().expect("REASON").check().await;
            //     if response.is_ok() {
            //         let update: Option<tauri_plugin_updater::Update> = response.unwrap();
            //         if update.is_some() {
            //             let update: tauri_plugin_updater::Update = update.unwrap();
            //             println!("Update available: {}", update.version);
            //         }
            //     }
            // });

            // Setup autostart from settings
            setup_autostart(app, settings.autostart.clone()).unwrap();

            // Setup the tray menu
            let separator = PredefinedMenuItem::separator(app)?;
            let settings = MenuItemBuilder::with_id("show_settings", "Open Settings").build(app)?;
            let data = MenuItemBuilder::with_id("show_data", "View Data").build(app)?;
            let check_for_updates =
                MenuItemBuilder::with_id("check_for_updates", "Check for Updates").build(app)?;
            let exit = PredefinedMenuItem::quit(app, Some("Exit"))?;

            let menu = MenuBuilder::new(app)
                .items(&[
                    &settings,
                    &data,
                    &separator,
                    &check_for_updates,
                    &separator,
                    &exit,
                ])
                .build()?;

            // let icon: Image = Image::

            // Setup the tray icon
            TrayIconBuilder::new()
                .tooltip("System Bridge")
                // .icon(icon)
                .menu(&menu)
                .menu_on_left_click(true)
                .on_menu_event(
                    move |app: &tauri::AppHandle, event: tauri::menu::MenuEvent| match event
                        .id()
                        .as_ref()
                    {
                        "show_settings" => {
                            create_window(app, "settings".to_string()).unwrap();
                        }
                        "show_data" => {
                            create_window(app, "data".to_string()).unwrap();
                        }
                        _ => (),
                    },
                )
                .on_tray_icon_event(|tray, event| match event.click_type {
                    ClickType::Left => {
                        // Show menu
                        // tray
                    }
                    ClickType::Double => {
                        let app = tray.app_handle();

                        create_window(app, "data".to_string()).unwrap();
                    }
                    _ => (),
                })
                .build(app)?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
