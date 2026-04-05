# final_project_ece3824

My idea for this project is to make a solar tracker using:
- A Raspberry Pi 3
- INA219 current sensor
- OLED display
- Mini Solar Panel (5V, 200mA)
- Breadboard
- Connector cables

The idea behind this project is to track the length of time the sun is out for on a given day, as a result this will have to run at an extended period of time with the raspberry pi constantly running data to the database. The purpose of the database in this case is to hold all of the data from each day that the tracker is running for. Seven days worth of data will be stored until the pi starts cycling out data for new data. Once the seven day max is hit, once the eighth day starts (at 12 midnight), the data from the first day will be completely erased and so on, in other words purging at midnight. If the raspberry pi loses power for any reason, the experiment will have to be reset manually as the Pi has to reboot completely. A successful run of this shows that after 7 days of operation, there will be a graphical display that shows the amount of time the sun is out for along with how much voltage, current, etc. is taken.

Small solar panels are very sensitive to light, this is good since it will give an accurate reading on whether sunlight is being detected. For the sake of this project, any voltage less than 1V will not be counted as sunlight otherwise it will be counted as sunlight. Something worth note is the INA219 has a shunt value resistance of .1 Ohms, which will affect the measured current values. Since readings occur every 30 seconds, each reading above 1V will count as 30 seconds of daylight, this will be factored into the amount of time the sun has been up for.

The OLED will display the last reading's time stamp and the estimated length of time the sun has been up for (Voltage greater than 1V)

Data collection will occur every 30 seconds where there will be a snapshot of the voltage being picked up by the solar panel every 30 seconds, sent to the database, and will be displayed on the website.

The frontend of the website will show a graph of the current time of the data taken and how much voltage the solar tracker has picked up at the time. It will also give a comparison chart of previous days. It will display the total daily sun hours as a bar chart across all stored days, allowing trends to be seen at a glance.

The code will be written in python, it will be the easiest to write communication code between the website and the pi and writing code for the INA219 is very seamless. The database I plan on using will be the SQLite since it is lightweight for a Raspberry Pi 3. The plot for the data will show all of the points taken, once the mouse hovers over a point you will then be shown more details for how much voltage, current, power, etc that is generated. Plotly will be used as the graphical tool here since there is minimal work required to build in hover details.

Flask will be used as the website's framework, using periodic polling to update in real time. This means that flask backend queries SQLite every 30 seconds and serves the data as a JSON API endpoint to match the collection rate, which the frontend fetches and renders with Plotly. Flask exposes a /data endpoint that returns the last 7 days of readings as a JSON array. The SQLite database will use a single table with columns for id, timestamp, voltage_v, current_ma, and power_mw.

All of the materials are already in hand, there is no need for funding.
