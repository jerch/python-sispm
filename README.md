Python module for the Gembird SIS-PM USB outlet devices. Runs on Python 2.7/3.*

### Dependencies

* PyUSB


### Example
```python
from sispm import get_devices
from time import sleep

for device in get_devices():
    print device.info
    device.on(1)
    sleep(1)
    print device.status(1)
    device.off(1)
    print device.status('all')
```


### TODO

* planification
* tests
* PyPI package