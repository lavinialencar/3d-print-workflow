# Network basics: a fixed IP for your printer

**Applies to every printer.** Whatever the brand, the monitor and your slicer find the printer by its network address. If that address changes,
everything breaks with a confusing timeout. The fix takes ten minutes, once.

## Why a fixed IP

Routers hand out addresses ("DHCP") and are free to change them, for example after a power cut or when a new device joins. A printer that was at
`192.0.2.10` yesterday may be at `192.0.2.14` today. The cure is to **reserve** the address for that printer in the router, so the router always gives it the
same one.

## Reserve the IP in your router

### Find the printer's MAC address

The printer must be on. From your Mac:

```bash
ping -c 1 <printer-ip> >/dev/null; arp -a | grep "<printer-ip>)"
```

You get something like `0:11:22:a:44:5b`. <!-- scan-ignore: fake example -->

> **Trap:** macOS drops leading zeros in each pair. The `0` and the `a` here really are `00` and `0a`. Pad every single-character
> pair with a zero before typing it into the router: `00:11:22:0a:44:5b`. <!-- scan-ignore: fake example -->

Most printers also show their MAC on a network-info screen, or on a label.

### Create the reservation

Every router names this differently. Look under DHCP or LAN settings for **Address Reservation**, **Static Lease**, **Reserved IP** or **Manual
Assignment**. Add an entry with the printer's MAC and the IP you want, enable it, and save.

**Do it while no print is running.** Some routers restart their address service when you save, and a printer that drops off the Wi-Fi in the middle of a
long print can fail it.

> **Checkpoint:** after the reservation (and a printer reboot, if you like), `ping <printer-ip>` still answers, and the port your printer family uses is open
> (`nc -z <printer-ip> 8883 && echo open` for Bambu; the Moonraker or OctoPrint web port for the others).

## "It does not answer"

If a reading times out and the address does not answer at all, the printer is simply **powered off** or off the Wi-Fi. That is by far the most common
cause, and worth checking before anything else. A quick way to tell "my network is broken" from "the printer is off":

```bash
ping -c 2 <router-ip>        # should answer; if not, the problem is your computer or Wi-Fi
ping -c 2 <printer-ip>       # if the router answers and this does not, the printer is the silent one
```

## Security notes

- Never forward the printer's ports through your router to the internet.
- Keep access codes and API keys out of chat logs, notes, screenshots and repositories.
- Anyone on your Wi-Fi can reach a printer on your LAN. Use a strong Wi-Fi password, and consider a separate network for IoT devices.
- Local access codes are passwords. If one leaks, regenerate it on the printer and update your config.

Next: [03 The Bambu Lab track](03-bambu-lab-track.md) or [05 Other printers](05-other-printers.md).
