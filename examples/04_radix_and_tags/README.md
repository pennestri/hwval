# 04 · Radix and log tags

Demonstrates `scope`, `msg_id`, `msg` and `radix` kwargs. Captures the
emitted log records so you can see how each kwarg ends up in the message.

## Run

```bash
uv run python examples/04_radix_and_tags/example.py
```

## What you'll see

A list of formatted log lines, one per check, like:

```
WARNING [reg_model] ID_REG16 PASS: REG16 readback  value=0xCAFE expected=0xCAFE  match=MATCH_STD
```

## What it shows

| Step | Demonstrates                                                       |
| ---: | ------------------------------------------------------------------ |
| 1    | Default `Radix.HEX_BIN_IF_INVALID` for plain ints (decimal output) |
| 2    | `Radix.HEX` formatting                                             |
| 3    | `Radix.BIN` formatting                                             |
| 4    | Sequences join without separators under `Radix.HEX`                 |
| 5    | `scope=` and `msg_id=` are prepended to the message                |
| 6    | UVVM-compatible positional `MatchStrictness` argument              |