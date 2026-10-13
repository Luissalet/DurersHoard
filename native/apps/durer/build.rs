// Modified for Dürer's Hoard: detached engine, product identity and historical import.
//! Windows only: embed the app icon and version info (VERSIONINFO) into `durer.exe`.
//!
//! On every other target this does nothing. A missing resource compiler is a warning, so a
//! cross-compile from macOS or Linux still links, unless `VECTORCRAFT_REQUIRE_WINRES=1` turns it into
//! an error (for release builds).

fn main() -> Result<(), String> {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=../../assets/app-icon/durer.ico");
    println!("cargo:rerun-if-env-changed=VECTORCRAFT_REQUIRE_WINRES");
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows") {
        return Ok(());
    }
    let mut res = winresource::WindowsResource::new();
    res.set_icon("../../assets/app-icon/durer.ico")
        .set("ProductName", "Dürer")
        .set("FileDescription", "Dürer vector illustration editor")
        .set("CompanyName", "Dürer’s Hoard")
        .set("LegalCopyright", "Copyright (c) the Dürer authors. MIT OR Apache-2.0.")
        .set("OriginalFilename", "durer.exe")
        .set("InternalName", "durer");
    if let Err(e) = res.compile() {
        if std::env::var_os("VECTORCRAFT_REQUIRE_WINRES").is_some() {
            return Err(format!("embedding Windows resources failed: {e}"));
        }
        println!("cargo:warning=durer.exe built without icon/version resources: {e}");
    }
    Ok(())
}
