# Dürer's Hoard HTTP API

Loopback only (`127.0.0.1:5222` by default). Every request passes the shared Hoard Link guard (loopback `Host`, same-site
`Origin`, Fetch Metadata).

## Illustrations

| Route | What it does |
|---|---|
| `GET /api/health` | service, engine and GUI configured, data folder, Hoard Link block, `copilot` (true when the Faustus copilot is installed) |
| `GET /api/catalog` | the native VectorCraft tools and commands |
| `GET /api/illustrations` / `POST /api/illustrations` | list / create (title, optional canvas size and units) |
| `POST /api/illustrations/import` | import a source file as a new illustration |
| `GET /api/illustrations/{id}` | one illustration (id, title, `hoard://` reference) |
| `POST /api/illustrations/{id}/actions` | run native actions (`inspect_document`, `draw_shape`, `transform`, `set_paint`, ...) |
| `POST /api/illustrations/{id}/export` | export SVG / PNG / PDF |
| `GET /api/illustrations/{id}/preview`, `/thumbnail`, `/native`, `/files/{area}/{filename}` | preview, thumbnail, project download, project files |
| `POST /api/illustrations/{id}/open-gui` | open the project in VectorCraft |
| `POST /api/native/dispatch` | call one native tool |
| `GET /api/operations/{id}` | receipt of an operation of this service lifetime |

## Faustus copilot (`/api/copilot/*`)

Mounted by Hoard Link's `install_copilot` from `durer_hoard/api.py`; absent with `HOARD_COPILOT=0` or a Hoard Link without it.

| Route | What it does |
|---|---|
| `GET /api/copilot/info` | `{app_id: "durer", app_name, data_space_id, panel_url, server, tool_server_id, settings_url}`; the data space id is stable (`data/copilot-space-id`); 503 when Faustus cannot be reached |
| `GET /api/copilot/panel.js` | the `<faustus-chat>` element, served by Faustus through the relay |
| `POST /api/copilot/proxy` | `{path, method, headers?, body? \| raw_body?, content_type?}` to Faustus; chat turns stream as Server-Sent Events; the Faustus token stays on the server, `origin.app_id` / `data_space_id` are forced; only `/api/hoard-copilot/`, `/api/chat/`, `/api/session(s)` and `/api/chat_stream` paths are allowed, anything else answers 400 |
| `GET /api/copilot/launcher.js` | the floating button and side panel script, added to every HTML page the app serves |

The page side is `window.hoardCopilot` (`durer_hoard/static/copilot.js`): `context(base)` returns `project`, `active_objects`
(the open illustration and the selected objects, read with `inspect_document`) and `view.editor` (a half filled dialog or
transform values not yet applied); `onTurnEnd(detail)` re-reads the illustration, objects and library.
