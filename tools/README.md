# Tools

Standalone developer-facing utilities for `hwval`. None of these are
required to use the library itself.

| Folder                                | What it is                                                                   |
| ------------------------------------- | ---------------------------------------------------------------------------- |
| [seg_config_gui/](seg_config_gui/)         | Self-contained HTML/JS form for building a `hwval.yml` for `SegDocument`. No server. |
| [seg_config_gui_flask/](seg_config_gui_flask/) | Pure-Python Flask app. Server-side YML generation and validation. |

The Flask app is a drop-in replacement for the static HTML form
when you want the validation rules to live in Python (and the
real `hwval.docs.load_seg_config` loader) rather than in
duplicated JS. Pick whichever fits the deployment story.
