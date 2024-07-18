import re
import subprocess
import threading
import time
import platform
from BufferedWriter import BufferedWriter


class Server:
    def __init__(self, address, description, color, path_logfile, ping_delay, element_count, amt_of_pings=5):
        self.address = address
        self.description = description
        self.color = color
        self.time_data = []
        self.ping_data = []
        self.loss_data = []
        self.jitter_data = []
        self.curve = None
        self.jitter_curve = None
        self.packetloss_curve = None
        self.ping_delay = ping_delay
        self.amt_of_pings = amt_of_pings
        self.path_logfile = path_logfile
        self.element_count = element_count
        self.writer = BufferedWriter(address.replace(".", "_")+"_log.txt", 4 * 1024) #4kB should lead to roughly one save per 10 min
        self.network_ping_thread = threading.Thread(target=self.collect_network_pings_data)
        self.network_ping_thread.daemon = True
        self.network_ping_thread.start()

    def get_maximum_in_data(self):
        maximum = 0
        for i in range(len(self.ping_data)):
            if self.ping_data[i] > maximum:
                maximum = self.ping_data[i]
            if self.loss_data[i] > maximum:
                maximum = self.loss_data[i]
        return maximum

    def collect_network_pings_data(self):
        while True:
            time_in_sec = time.time()
            try:  # "-c", self.amt_of_pings
                # obtain data
                output = None
                if platform.system().lower() == 'windows':
                    output = subprocess.run(["ping", "-n", str(self.amt_of_pings), self.address], capture_output=True,
                                            text=True,
                                            universal_newlines=True,
                                            creationflags=subprocess.CREATE_NO_WINDOW,
                                            encoding='latin-1')
                else:
                    output = subprocess.run(["ping", "-c", str(self.amt_of_pings), self.address], capture_output=True,
                                            text=True,
                                            universal_newlines=True,
                                            encoding='latin-1')

                # extract data
                min_ping = -1
                max_ping = -1
                avg_ping = -1
                lost_packets = 0
                loss_rate = 0.0
                for line in output.stdout.split("\n"):
                    #print(line)
                    if "Lost =" in line:
                        lost_packets = int(line.split("Lost = ")[-1].split(" ")[0])
                    elif "Verloren =" in line:
                        lost_packets = int(line.split("Verloren = ")[-1].split(" ")[0])
                    elif "Minimum" in line:
                        values = re.findall(r'\d+', line)
                        values = list(map(int, values))
                        if len(values) == 3:
                            min_ping = values[0]
                            max_ping = values[1]
                            avg_ping = values[2]

                if lost_packets != 0:
                    loss_rate = lost_packets / self.amt_of_pings
                #print(lost_packets)

                self.time_data.append(time_in_sec)
                self.ping_data.append(avg_ping)
                self.jitter_data.append(max_ping - min_ping)
                self.loss_data.append(loss_rate * 100)

                self.writer.write(f"{time_in_sec};{avg_ping};{min_ping};{max_ping};{loss_rate}")

                #if self.address == "23.94.198.153":
                 #   print(len(self.ping_data))

                if len(self.ping_data) > self.element_count:
                    self.time_data.pop(0)
                    self.ping_data.pop(0)
                    self.jitter_data.pop(0)
                    self.loss_data.pop(0)

            except subprocess.CalledProcessError as e:
                print(f"Ping failed with error: {e.output}")

            time_taken = time.time() - time_in_sec
            time_to_sleep = self.ping_delay
            if time_taken > self.ping_delay:
                time_to_sleep = 0
            else:
                time_to_sleep = self.ping_delay - time_taken
            # print(f"time taken: {time_taken}    time to sleep: {time_to_sleep}")
            time.sleep(time_to_sleep)