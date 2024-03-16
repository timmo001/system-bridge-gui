// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::error::Error;

use tauri::App;
use tauri::{WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_autostart::MacosLauncher;
use tauri_plugin_autostart::ManagerExt;
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

    let settings: String = std::fs::read_to_string(settings_path).unwrap();
    let settings: Settings = serde_json::from_str(&settings).unwrap();

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

    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        // .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_shell::init())
        .setup(move |app: &mut App| {
            // Setup autostart from settings
            setup_autostart(app, settings.autostart).unwrap();

            let url: tauri::Url = format!(
                "{}/app/{}.html?apiPort={}&token={}",
                base_url,
                "data",
                settings.api.port.clone(),
                settings.api.token.clone()
            )
            .parse()
            .unwrap();
            WebviewWindowBuilder::new(app, "main".to_string(), WebviewUrl::External(url))
                .inner_size(WINDOW_WIDTH, WINDOW_HEIGHT)
                .title("Data | System Bridge")
                .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
