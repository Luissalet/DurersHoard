// Modified for Dürer's Hoard: detached engine, product identity and historical import.
//! Help → community and project links (the ArtCraft Discord, website, this app's page and its
//! GitHub repository). The commands return the URL; the frontend opens it.

use serde_json::{Value, json};

use super::*;

/// The app's id on getartcraft.com and GitHub.
pub const APP_ID: &str = "durer";
pub const DISCORD_URL: &str = "https://discord.gg/artcraft";
pub const WEBSITE_URL: &str = "http://127.0.0.1:8810";

/// This app's page on the website.
pub fn app_page_url() -> String {
    std::env::var("DURER_URL").unwrap_or_else(|_| "http://127.0.0.1:5222".into())
}

/// This app's source repository.
pub fn github_url() -> String {
    "https://github.com/Luissalet/DurersHoard".into()
}

pub fn specs() -> Vec<CommandSpec> {
    vec![
        cmd!(query "help.discord", "Historical source community", ["Help"], None, "{} → {url} original source community", always, |_, _| url(DISCORD_URL.into())),
        cmd!(query "help.website", "Hoard Hub", ["Help"], None, "{} → {url}", always, |_, _| url(WEBSITE_URL.into())),
        cmd!(query "help.appPage", "Dürer's Hoard", ["Help"], None, "{} → {url} this app's page", always, |_, _| url(app_page_url())),
        cmd!(query "help.github", "Dürer on GitHub", ["Help"], None, "{} → {url} source code, issues and releases", always, |_, _| url(github_url())),
        cmd!(query "help.links", "Links", [], None, "{} → {discord, website, appPage, github}", always, |_, _| {
            Ok(json!({ "discord": DISCORD_URL, "website": WEBSITE_URL, "appPage": app_page_url(), "github": github_url() }))
        }),
    ]
}

fn url(u: String) -> Result<Value> {
    Ok(json!({ "url": u }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn links() {
        let mut s = Session::new();
        assert_eq!(s.execute("help.discord", &json!({})).unwrap()["url"], "https://discord.gg/artcraft");
        assert_eq!(s.execute("help.appPage", &json!({})).unwrap()["url"], app_page_url());
        assert_eq!(s.execute("help.github", &json!({})).unwrap()["url"], "https://github.com/Luissalet/DurersHoard");
        assert_eq!(s.execute("help.links", &json!({})).unwrap()["website"], "http://127.0.0.1:8810");
    }
}
