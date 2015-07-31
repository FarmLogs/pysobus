# PySOBUS – Python ISOBUS Libraries

PySOBUS provides ISO 11783 (ISOBUS) message specifications and decoding tools for proprietary messages which are not publicly defined.

The initial focus is on messages that are relevant to yield calculation.  Currently supported are combines with AFS 700 or GreenStar 2600/2630 displays.

Message specifications are stored in [pysobus/message_definitions.csv](https://github.com/FarmLogs/pysobus/blob/master/pysobus/message_definitions.csv) in the following format:

* `pgn_id` – parameter group number
* `manufacturer` – equipment manufacturer, e.g. John Deere, Case, etc.
* `source_address` – CAN bus network address for message sender
* `pgn_length_bytes` – number of bytes per message
* `spn_start_position` – bit offset for the SPN (suspect parameter number) within the PGN message.  Format: {byte offset}.{bit offset} (ones based).  Examples: 1.1 => 0 bit offset, 2.3 => 10 bit offset
* `spn_bit_length` – number of bits for this SPN
* `spn_id` – unique identifier (optional)
* `spn_name` – descriptive functional name for SPN
* `spn_description` – SPN description
* `scale_factor` – scale factor/multiplier for SPN (float)
* `offset` – fixed offset for SPN (float)
* `units` – SPN units, e.g. degrees, kg/sec, etc

### Installation

Install from PyPI:

```shell
pip install pysobus
```

Alternatively, you can clone this repository and install it via `setup.py`:

```shell
git clone https://github.com/FarmLogs/pysobus.git
cd pysobus/
python setup.py install
```

### Usage

```python
>>> from pysobus.parser import Parser
>>> p = Parser()
>>> p.parse_message('18FEF31C3D422397722E724B')
{'info': {'header': '18FEF31C',
  'message': '18FEF31C3D422397722E724B',
  'payload_bytes': ['3D', '42', '23', '97', '72', '2E', '72', '4B'],
  'payload_int': 5436458769886429757,
  'pgn': 65267,
  'priority': 6,
  'source': 28,
  'timestamp': 0},
 'pgn': 65267,
 'spn_vals': {'Latitude': 43.56703329999999, 'Longitude': -83.4225806}}
```

Additional example messages with decoded results are available in  [pysobus/tests](https://github.com/FarmLogs/pysobus/tree/master/pysobus/tests).
