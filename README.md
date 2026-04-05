## trmnl python client

a humble python sdk for [trmnl](https://usetrmnl.com). based on [usetrmnl/trmnl-firmware](https://github.com/usetrmnl/trmnl-firmware).

```bash
pip install git+https://github.com/davidheineman/trmnl.git
```

```bash
# relevant env vars
export TRMNL_API_KEY="..."
export TRMNL_USER_API_KEY="..."
export TRMNL_PLUGIN_UUID="..."
export TRMNL_MAC_ADDRESS="..."
```

### usage

```python
from trmnl import TRMNL

t = TRMNL(plugin_uuid="...", mac_address="...")

t.status()                                  # device info
t.show({"title": "hi", "body": "hello"})    # push content
t.current_screen()                          # get current screen
t.next_screen()                             # advance to next screen
t.download_screen("screen.png")             # save screen image
t.set_markup(t.plugin_uuid, "<div>{{ title }}</div>") # set markup on a plugin
```

there's a cli as well, but you can ask claude about that.