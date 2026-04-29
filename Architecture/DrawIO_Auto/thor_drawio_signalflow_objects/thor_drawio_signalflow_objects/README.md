# THOR UML Signalflow Objects

This version models and renders:

- Blocks as UML-like objects
- Ports as explicit objects with own attributes
- Nets/Buses as explicit signal objects with own attributes
- Wires as small attachment edges from ports to signal objects
- Top-down pages for hierarchy

This is the important distinction:

```text
Port object  ── wire ──  Net/Bus object  ── wire ── Port object
```

The net/bus is not just an edge anymore. It is a real object.

## Inspect metadata in draw.io

Select any block, port, net/bus object, or wire:

Right click → Edit Data

You will see fields such as:

- `kind`
- `object_id`
- `object_name`
- `stereotype`
- `type`
- `endpoint_count`
- `endpoints`
- `parent_block_id`
- `fqid`
- `attr_*`
- `attributes_json`

## Run

```bash
python example_signalflow.py
```
