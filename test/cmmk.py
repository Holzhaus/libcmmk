#!/usr/bin/env python3
import atexit
import cmd
import contextlib
import hexdump
import sys
import usb
import readline


@contextlib.contextmanager
def cmmk_device(product_id=None):
    kwargs = {
        'idVendor': 0x2516,
    }
    if product_id is not None:
        kwargs['idProduct'] = product_id

    # find our device
    dev = usb.core.find(**kwargs)


    # was it found?
    if dev is None:
        raise ValueError('Device not found')

    reattach = False
    if dev.is_kernel_driver_active(1):
        print('Detaching kernel driver...')
        reattach = True
        dev.detach_kernel_driver(1)
    try:
        cfg = dev.get_active_configuration()
        intf = cfg[(1,0)]
        ep_in = usb.util.find_descriptor(intf,custom_match=lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_IN)
        ep_out = usb.util.find_descriptor(intf,custom_match=lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_OUT)
        yield ep_in, ep_out
    finally:
        if reattach:
            print('Reattaching kernel driver...')
            usb.util.dispose_resources(dev)
            dev.attach_kernel_driver(1)


class CmmkShell(cmd.Cmd):
    intro = 'Welcome to the cmmk shell.   Type help or ? to list commands.\n'
    prompt = '(cmmk) '
    transcript = []

    def __init__(self, usb_entrypoints, *args, histfile='.cmmk_history', **kwargs):
        self.ep_in, self.ep_out = usb_entrypoints
        super().__init__(*args, **kwargs)

        if hasattr(readline, 'read_history_file'):
            try:
                readline.read_history_file(histfile)
            except IOError:
                pass
            atexit.register(self.save_history, histfile)

    def save_history(self, histfile):
        readline.set_history_length(1000)
        readline.write_history_file(histfile)

    def do_hex(self, arg):
        'Send up to 64 hex bytes to device:  hex DEADBEEF001122...'
        if not arg:
            return

        try:
            data = hexdump.dehex(arg.ljust(128, '0'))
            if len(data) > 64:
                raise ValueError('Input too long')
        except Exception as e:
            print('Error occured: %r' % e)
            return

        self.ep_out.write(data)
        hexdump.hexdump(self.ep_in.read(64))

    def do_eof(self, arg):
        return self.do_exit(arg)

    def do_exit(self, arg):
        'Exit the shell:  EXIT'
        return True

    def precmd(self, line):
        return line.lower()


if __name__ == '__main__':
    with cmmk_device() as ep:
        CmmkShell(ep).cmdloop()
