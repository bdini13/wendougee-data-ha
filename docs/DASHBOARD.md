# Espresso dashboard

`dashboards/espresso.yaml` is the source-controlled Home Assistant dashboard for
the **WENDOUGEE DATA S**. It uses only built-in cards, so it does not require a
custom frontend card collection. It is installed as the sidebar dashboard
`Espresso` on the target host. Live sensor graphs avoid fixed unit-dependent
ranges, so the same configuration remains accurate when HA converts °C/bar/mL
to °F/psi/fluid ounces.

## What it shows

- current temperatures, pressure, volume, connectivity, alarm and activity;
- recent-shot time and volume;
- daily changes in the persistent observed-shot and observed-water totals;
- recent temperature, pressure, connectivity and cleaning history;
- reported boiler targets/enables and cleaning configuration;
- independent brew/steam desired schedule helpers, clearly marked inactive.

The word **observed** is intentional. A complete shot can occur between polls,
so the counters are a conservative lower bound rather than an audit-grade meter.
Pumped volume is a machine-reported hydraulic value, not cup yield or household
water consumption.

## Schedule safety boundary

The desired schedule defaults to 07:00–09:00 in Home Assistant's
`America/New_York` timezone. The helpers do not call the machine. No schedule
automation should be enabled until supervised tests establish, on the local DATA
S, the boiler-write polarity, response correlation, complete readback,
persistence, concurrent-app behavior and failure recovery. A network-controlled
boiler is not a hardware safety interlock.

## Artwork

The dashboard image is
`custom_components/wendougee_data/images/wendougee-data-s-white-rose-gold.png`.
It is original AI-generated artwork created for this project from a descriptive
prompt, with the machine configuration and colorway visually cross-checked
against the [Espresso Outlet product page](https://espressooutlet.com/products/wendougee-data-s-espresso-machine).
The retailer's product photography is not copied into this repository because
the page does not grant redistribution rights.
