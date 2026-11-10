# Archived visual types

These contracts are **not part of the core**. The core ships seven types —
`header`, `card`, `kpi`, `column`, `line`, `bar`, `table` — and `slots.contracts()`
loads only the YAML files one directory up.

Everything here is probe-verified and still correct (each file cites its probe).
It is archived to keep the core small and learnable, not because it is wrong.

To use these types, put this directory on the visuals search path in your
guidelines:

```yaml
extensions:
  custom_visuals:
    search_path: ["<path to>/blueprint/visuals/archive"]
```

Relative entries resolve against the guidelines file that declares them, exactly
like `layouts.search_path`.

A spec naming one of these types without that opt-in is refused with
"unknown type", naming the types that are loaded.
