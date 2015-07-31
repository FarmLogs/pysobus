import os
import re
import logging
from collections import defaultdict

import spanner as sp

MASK_2_BIT = ((1 << 2) - 1)
MASK_3_BIT = ((1 << 3) - 1)
MASK_8_BIT = ((1 << 8) - 1)


def msg_to_header_info_and_payload(hex_message, timestamp=0):
    """
    decode a hex message into its core components:
    pgn, source and payload integer
    >>> import pprint
    >>> pprint.pprint(msg_to_header_info_and_payload('60FEF31CD1EE2397FA7C744B')) #doctest: +NORMALIZE_WHITESPACE
    {'header': '60FEF31C',
     'message': '60FEF31CD1EE2397FA7C744B',
     'payload_bytes': ['D1', 'EE', '23', '97', 'FA', '7C', '74', '4B'],
     'payload_int': 5437108065862414033,
     'pgn': 65267,
     'priority': 0,
     'source': 28,
     'timestamp': 0}
    """

    # J1939 header info:
    # http://www.ni.com/example/31215/en/
    # http://tucrrc.utulsa.edu/J1939_files/HeaderStructure.jpg
    header_hex = hex_message[:8]
    header = int(header_hex, 16)

    src = header & MASK_8_BIT
    header >>= 8
    pdu_ps = header & MASK_8_BIT
    header >>= 8
    pdu_pf = header & MASK_8_BIT
    header >>= 8
    res_dp = header & MASK_2_BIT
    header >>= 2
    priority = header & MASK_3_BIT

    pgn = res_dp
    pgn <<= 8
    pgn |= pdu_pf
    pgn <<= 8
    if pdu_pf >= 240:
        # pdu format 2 - broadcast message. PDU PS is an extension of
        # the identifier
        pgn |= pdu_ps

    payload_bytes = re.findall('[0-9a-fA-F]{2}', hex_message[8:])
    payload_int = int(''.join(reversed(payload_bytes)), 16)

    return {'pgn': pgn,
            'source': src,
            'priority': priority,
            'payload_int': payload_int,
            'payload_bytes': payload_bytes,
            'header': header_hex,
            'message': hex_message,
            'timestamp': timestamp}


class Parser(object):
    def __init__(self):
        # load PGN/SPN definitions from text. Use Spanner's tables library
        # to group definitions by pgn, manufacturer and source address
        self.pgn_src_to_parser = dict()
        key_cols = ['pgn_id', 'manufacturer', 'pgn_length_bytes', 'source_address']
        val_cols = ['opcode', 'spn_name', 'spn_description',
                    'spn_start_position', 'spn_bit_length', 'scale_factor',
                    'offset', 'units']
        fn = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'message_definitions.csv')
        pgn_to_spn_specs = sp.tables.load_dict(fn, key_cols, val_cols, delimiter=',')

        # create PGN/SPN decoders according to the message definitions
        for pgn_def, spn_defs in pgn_to_spn_specs.items():
            pgn, mfr, num_bytes, src = pgn_def
            # group SPN decoders by opcode (if applicable)
            opcode_to_spns = defaultdict(list)
            opcode_parser = None
            for spn_def in spn_defs:
                spn_decoder = SPN(pgn,
                                  spn_def['spn_name'],
                                  spn_def['spn_description'],
                                  spn_def['spn_start_position'],
                                  spn_def['spn_bit_length'],
                                  scale=spn_def['scale_factor'],
                                  offset=spn_def['offset'],
                                  units=spn_def['units'])

                if spn_def['spn_name'].lower() == 'pgn usage opcode':
                    opcode_parser = spn_decoder
                else:
                    opcode = spn_def['opcode']
                    if opcode == '':
                        opcode = None
                    opcode_to_spns[opcode].append(spn_decoder)

            for opcode, spns in opcode_to_spns.items():
                # verify that we found an opcode parser message spec if any of
                # the SPN definitions specificy an opcode
                if any(opcode_to_spns.keys()) and not opcode_parser:
                    raise RuntimeError('Opcode decoder not found for PGN: %s, src: %s'
                                       % (pgn, src))

                self.pgn_src_to_parser[(pgn, src)] = PGN(pgn, num_bytes,
                                                         src, opcode_to_spns,
                                                         opcode_parser=opcode_parser)

        # PGN129029 is a different animal, and has its own subclass - see below
        self.pgn_src_to_parser[(129029, 28)] = PGN129029()

    def parse_message(self, hex_str, timestamp=0):
        try:
            info = msg_to_header_info_and_payload(hex_str, timestamp)
        except ValueError:
            logging.warning('Could not parse message: ' + hex_str)
            return None

        key = info['pgn'], info['source']
        if key in self.pgn_src_to_parser:
            return self.pgn_src_to_parser[key].parse_from_info_dict(info)


class PGN(object):
    def __init__(self, pgn, num_bytes, source_address,
                 opcode_to_spns, opcode_parser=None):
        self.pgn = pgn
        self.nbytes = num_bytes
        self.source_address = source_address
        self.opcode_to_spns = opcode_to_spns
        self.opcode_parser = opcode_parser

    def parse_message(self, message, timestamp=0):
        info = msg_to_header_info_and_payload(message, timestamp)
        return self.parse_from_info_dict(info)

    def parse_from_info_dict(self, info):
        if info['pgn'] != self.pgn:
            raise RuntimeError('Invalid PGN! Expected {}, got {}'.format(self.pgn, info['pgn']))

        if info['source'] != self.source_address:
            raise RuntimeError('Invalid source! Expected {}, got {}'.format(self.source_address, info['source']))

        if self.opcode_parser:
            opcode = self.opcode_parser.parse_from_int(info['payload_int'])
        else:
            opcode = None

        return {'pgn': self.pgn,
                'info': info,
                'spn_vals': {s.spn_name: s.parse_from_int(info['payload_int'])
                             for s in self.opcode_to_spns[opcode]}}


class SPN(object):
    def __init__(self, pgn, spn_name, description, position, num_bits,
                 scale=1, offset=0, signed=False, units=None):
        self.pgn = pgn
        self.spn_name = spn_name
        self.desc = description
        self.nbits = num_bits
        self.units = units
        self.scale = scale
        self.offset = offset
        self.signed = signed

        # parse bit offset from decimal format in the message spec file:
        # {byte pos}.{bit offset}
        byte_offs = int(position) - 1
        bit_offs = max(0, int(position * 10) % 10 - 1)
        self.pos = byte_offs * 8 + bit_offs

    def parse_from_int(self, payload_int):
        """
        >>> s = SPN('test', 'test', 'test', 1.4, 8, scale=1e-3, offset=3)
        >>> s.parse_from_int(5437108070157381327)
        3.217
        """
        x = payload_int >> self.pos
        x &= (1 << self.nbits) - 1
        if self.signed and x & (1 << (self.nbits - 1)):
            x -= 1 << self.nbits

        return x * self.scale + self.offset


# PGN 129029, the NMEA navigation message, is multi-part, and a little more
# complicated to handle.  For the time being, we are leaving it as a separate
# class
# See the following link for details:
# http://hemispheregnss.com/gpsreference/GNSSPositionData.htm

class PGN129029(PGN):
    def __init__(self):
        pgn = 129029
        spns = []

        for name, offset, length in (('Latitude', 9, 64),
                                     ('Longitude', 17, 64)):
            spns.append(SPN(pgn, name, name, offset, length,
                            scale=1e-16, signed=True))

        super(PGN129029, self).__init__(pgn, 51, 28, {None: spns})

        # create "fake spns" to decode the sequence group and ID
        self.__seq_num_spn = SPN(0, 'Sequence ID', '', 1, 4)
        self.__seq_group_spn = SPN(0, 'Sequence Group', '', 1.5, 4)
        self.__group_to_timestamp = dict()
        self.__group_to_seq_to_payload = defaultdict(lambda: {})

    def parse_message(self, message, timestamp=0):
        """
        Decode multi-part message; nothing should be returned until the last part
        >>> p = PGN129029()
        >>> p.parse_message('61F8051C86FF015F08BC0201')
        >>> p.parse_message('61F8051C840000000023000B')
        >>> p.parse_message('61F8051C812B801401279131')
        >>> p.parse_message('61F8051C802FCC923F73E755')
        >>> p.parse_message('61F8051C85510087006BF2FF')
        >>> p.parse_message('61F8051C83736BF4926E420B')
        >>> import pprint
        >>> pprint.pprint(p.parse_message('61F8051C82090600A1A1478C')) #doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
        {'info': {'header': '61F8051C',
                  'message': '61F8051C2FCC923F73E7552...',
                  'payload_bytes': ['2F',... '01'],
                  'payload_int': 39822884687169358196...,
                  'pgn': 129029,
                  'priority': 0,
                  'source': 28,
                  'timestamp': 0},
         'pgn': 129029,
         'spn_vals': {<parser.SPN object at ...>: 43.493333851236464,
                      <parser.SPN object at ...>: -83.44462596127045}}
        """
        info = msg_to_header_info_and_payload(message, timestamp)
        return self.parse_from_info_dict(info)

    def parse_from_info_dict(self, info):
        payload_int = info['payload_int']
        seq_grp = self.__seq_group_spn.parse_from_int(payload_int)

        if seq_grp in self.__group_to_timestamp:
            # check for stale sequence group entries - if the timestamp
            # difference is more than ~1 second, these aren't really from the
            # same sequence group
            if abs(info['timestamp'] - self.__group_to_timestamp[seq_grp]) > 2:
                self.__group_to_seq_to_payload[seq_grp].clear()

        self.__group_to_timestamp[seq_grp] = info['timestamp']
        seq_to_payload = self.__group_to_seq_to_payload[seq_grp]
        seq_num = self.__seq_num_spn.parse_from_int(payload_int)

        # skip the first byte (sequence number)
        seq_to_payload[seq_num] = info['payload_bytes'][1:]

        if len(seq_to_payload.keys()) == 7:
            # the gang's all here - assemble the payloads
            all_payload_bytes = []
            try:
                for seq_num in xrange(7):
                    all_payload_bytes.extend(seq_to_payload[seq_num])
            except KeyError:
                logging.warning('Couldn\'t find all the keys: ' +
                                str(seq_to_payload.keys()))
                return None
            finally:
                seq_to_payload.clear()

            full_msg = info['header'] + ''.join(all_payload_bytes)
            full_msg_info = msg_to_header_info_and_payload(full_msg)
            return super(PGN129029, self).parse_from_info_dict(full_msg_info)
