use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();

            // Open DevTools automatically in dev builds for debugging
            #[cfg(debug_assertions)]
            window.open_devtools();

            // Position flush with right edge of primary monitor, vertically centered.
            // margin=0 so the orb's slide animation disappears behind the screen bezel.
            if let Some(monitor) = window.primary_monitor()? {
                let screen = monitor.size();
                let win = window.outer_size()?;
                let x = (screen.width as i32).saturating_sub(win.width as i32);
                let y = (screen.height as i32).saturating_sub(win.height as i32) / 2;
                window.set_position(tauri::PhysicalPosition::new(x, y))?;
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
