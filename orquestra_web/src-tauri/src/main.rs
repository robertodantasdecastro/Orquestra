#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::path::PathBuf;
use std::process::Command;

fn candidate_roots() -> Vec<PathBuf> {
    let mut roots = Vec::new();
    if let Ok(value) = env::var("ORQUESTRA_GRAPHICAL_INSTALLER_ROOT") {
        roots.push(PathBuf::from(value));
    }
    if let Ok(value) = env::var("ORQUESTRA_ROOT") {
        roots.push(PathBuf::from(value));
    }
    if let Ok(current) = env::current_dir() {
        roots.push(current.clone());
        for ancestor in current.ancestors() {
            roots.push(ancestor.to_path_buf());
        }
    }
    if let Ok(exe) = env::current_exe() {
        for ancestor in exe.ancestors() {
            roots.push(ancestor.to_path_buf());
        }
    }
    roots
}

fn find_root() -> Result<PathBuf, String> {
    for root in candidate_roots() {
        if root.join("scripts/install_orquestra_macos_full.sh").exists() {
            return Ok(root);
        }
        if root.join(".payload/scripts/install_orquestra_macos_full.sh").exists() {
            return Ok(root.join(".payload"));
        }
    }
    Err("Nao encontrei scripts do Orquestra. Abra pelo DMG gerado ou defina ORQUESTRA_ROOT.".to_string())
}

fn run_script(script: &str, args: &[&str]) -> Result<String, String> {
    let root = find_root()?;
    let script_path = root.join("scripts").join(script);
    if !script_path.exists() {
        return Err(format!("Script ausente: {}", script_path.display()));
    }
    let output = Command::new("/bin/bash")
        .arg(script_path)
        .args(args)
        .env("ORQUESTRA_ROOT", &root)
        .output()
        .map_err(|err| format!("Falha ao executar script: {err}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let payload = format!(
        "{{\"success\":{},\"code\":{},\"stdout\":{},\"stderr\":{}}}",
        output.status.success(),
        output.status.code().unwrap_or(-1),
        json_string(&stdout),
        json_string(&stderr)
    );
    Ok(payload)
}

fn json_string(value: &str) -> String {
    let mut out = String::from("\"");
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

#[tauri::command]
fn installer_preflight() -> Result<String, String> {
    run_script("install_orquestra_macos_full.sh", &["--check-only", "--json", "--no-tty", "--no-secrets-output"])
}

#[tauri::command]
fn installer_build_plan() -> Result<String, String> {
    run_script("install_orquestra_macos_full.sh", &["--check-only", "--json", "--no-tty", "--no-secrets-output"])
}

#[tauri::command]
fn installer_run_plan(required_only: bool, optional_csv: String, configure_env: bool) -> Result<String, String> {
    let mut args = vec!["--yes", "--emit-events", "--no-tty", "--no-secrets-output"];
    if required_only {
        args.push("--required-only");
    }
    if !optional_csv.trim().is_empty() {
        args.push("--with-optional");
        args.push(Box::leak(optional_csv.into_boxed_str()));
    }
    if configure_env {
        args.push("--configure-env");
    }
    run_script("install_orquestra_macos_full.sh", &args)
}

#[tauri::command]
fn installer_cancel() -> Result<String, String> {
    Ok("{\"success\":true,\"message\":\"Cancelamento registrado; nenhuma execucao em background ativa nesta V1.\"}".to_string())
}

#[tauri::command]
fn installer_open_external_url(url: String) -> Result<String, String> {
    Command::new("/usr/bin/open")
        .arg(url)
        .status()
        .map_err(|err| format!("Falha ao abrir URL: {err}"))?;
    Ok("{\"success\":true}".to_string())
}

#[tauri::command]
fn installer_store_secret(secret_ref: String, value: String) -> Result<String, String> {
    if secret_ref.trim().is_empty() || value.is_empty() {
        return Err("secret_ref e value sao obrigatorios.".to_string());
    }
    let output = Command::new("/usr/bin/security")
        .args(["add-generic-password", "-U", "-s", "ai.orquestra.secrets", "-a", &secret_ref, "-w", &value])
        .output()
        .map_err(|err| format!("Falha ao chamar Keychain: {err}"))?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    Ok(format!("{{\"success\":true,\"secret_ref\":{}}}", json_string(&secret_ref)))
}

#[tauri::command]
fn uninstaller_scan() -> Result<String, String> {
    run_script("uninstall_orquestra_macos_full.sh", &["--dry-run", "--json", "--no-tty", "--no-secrets-output"])
}

#[tauri::command]
fn uninstaller_build_plan(mode: String) -> Result<String, String> {
    let mode_ref = Box::leak(mode.into_boxed_str());
    run_script("uninstall_orquestra_macos_full.sh", &["--dry-run", "--json", "--mode", mode_ref, "--no-tty", "--no-secrets-output"])
}

#[tauri::command]
fn uninstaller_run_plan(mode: String, backup_data: bool, confirm_remove_all: bool) -> Result<String, String> {
    let mode_ref = Box::leak(mode.into_boxed_str());
    let mut args = vec!["--mode", mode_ref, "--yes", "--emit-events", "--no-tty", "--no-secrets-output"];
    if backup_data {
        args.push("--backup-data");
    }
    if confirm_remove_all {
        args.push("--confirm-remove-all");
    }
    run_script("uninstall_orquestra_macos_full.sh", &args)
}

#[tauri::command]
fn uninstaller_create_backup() -> Result<String, String> {
    run_script("uninstall_orquestra_macos_full.sh", &["--select", "memory,rag_indexes,osint,workspace,db", "--backup-data", "--dry-run"])
}

#[tauri::command]
fn uninstaller_cancel() -> Result<String, String> {
    Ok("{\"success\":true,\"message\":\"Cancelamento registrado; nenhuma execucao em background ativa nesta V1.\"}".to_string())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            installer_preflight,
            installer_build_plan,
            installer_run_plan,
            installer_cancel,
            installer_open_external_url,
            installer_store_secret,
            uninstaller_scan,
            uninstaller_build_plan,
            uninstaller_run_plan,
            uninstaller_create_backup,
            uninstaller_cancel
        ])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar o shell desktop do Orquestra");
}
