# final_project_ece3824

My idea for this project is to make an electromyography (EMG) using:
- A raspberry pi
- ADS1115 ADC Module
- Myoware muscle sensor kit
- OLED display
- 5V power supply
- Breadboard
- Connector cables

Breadboards and connector cables aren't difficult to attain. I will buy a raspberry pi that supports external power sources, the ADS1115 should do fine as an analog to digital converter. I will also buy the ADS1115 ADC Module since it has a bit converter that will be able to pick up the small signals emitted by the muscle. The rest of the material may need to be bought.

The type of data to be collected will be the muscle activation. The general structure is as follows:

Muscle -> Electrodes -> EMG Module -> ADC Module -> ADC Reading -> Raspberry Pi -> Web Dashboard

The data will be shown as a graph of the muscle activation over a recent time (this hasn't been decided yet).

