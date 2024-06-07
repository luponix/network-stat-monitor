import datetime
import re
import sys
import psutil
import subprocess
import threading
import safe_exit
from PyQt5 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
import time
import platform

changed_plot_y_max = 0
time_changed_y_max = 0
ping_plot_y_max = 0


class Server:
    def __init__(self, address, description, color, path_logfile, ping_delay, amt_of_pings=5):
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
        self.writer = BufferedWriter(address.replace(".", "_")+"_log.txt")
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
        global ping_plot_y_max
        global changed_plot_y_max
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
                    output = subprocess.run(["ping", "-n", str(self.amt_of_pings), self.address], capture_output=True,
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
                    # print(line)
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

                t = time.strftime("%D %T", time.gmtime(time.time()))
                # print(f"{t}     avg: {avg_ping}ms   variance: {max_ping-min_ping}ms   loss: {str(loss_rate*100)}%")

                if avg_ping > ping_plot_y_max:
                    ping_plot_y_max = avg_ping + 10
                    changed_plot_y_max = 1
                    time_changed_y_max = time_in_sec

                self.time_data.append(time_in_sec)
                self.ping_data.append(avg_ping)
                self.jitter_data.append(max_ping - min_ping)
                self.loss_data.append(loss_rate * 100)

                self.writer.write(f"{time_in_sec};{avg_ping};{min_ping};{max_ping};{loss_rate}")

                if len(self.ping_data) > PING_PLOT_ELEMENT_COUNT:
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


class BufferedWriter:
    def __init__(self, filename, buffer_size=1024 * 1024):
        self.filename = filename
        self.buffer_size = buffer_size
        self.buffer = []
        self.current_buffer_size = 0

    def write(self, line):
        line += '\n'
        self.buffer.append(line)
        self.current_buffer_size += len(line)
        if self.current_buffer_size >= self.buffer_size:
            self.flush()

    def flush(self):
        print("[Buffered Writer] flushed "+self.filename)
        with open(self.filename, 'a') as file:
            file.write(''.join(self.buffer))
        self.buffer = []
        self.current_buffer_size = 0

    def close(self):
        if self.buffer:
            self.flush()


def format_time(seconds):
    return datetime.datetime.fromtimestamp(seconds).strftime('%H:%M:%S')

class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [format_time(value) for value in values]



COLLECT_LOOP_CPU_UTIL_DELAY_IN_SEC = 0.1
COLLECT_LOOP_PING_DELAY_IN_SEC = 5.0
PING_PLOT_ELEMENT_COUNT = 400
SERVERS = [
    Server("194.59.206.166", "D.Cent", "#00FF00", "", COLLECT_LOOP_PING_DELAY_IN_SEC),       #1
    Server("107.175.134.202", "O:Ashburn", "#008080", "", COLLECT_LOOP_PING_DELAY_IN_SEC),
    Server("107.174.63.199", "O:Buffalo, NY", "#3366FF", "", COLLECT_LOOP_PING_DELAY_IN_SEC),
    Server("64.44.185.209", "O:Denver, CO", "#FFD700", "",COLLECT_LOOP_PING_DELAY_IN_SEC),

    Server("167.71.7.105", "Amsterdam 1", "#0F5733", "", COLLECT_LOOP_PING_DELAY_IN_SEC),    #1
    Server("23.94.198.153", "O:Chicago", "#00FFFF", "", COLLECT_LOOP_PING_DELAY_IN_SEC),
    Server("23.94.207.160", "O: Buffalo, NY2", "#4169E1", "", COLLECT_LOOP_PING_DELAY_IN_SEC),
    Server("64.44.185.231", "O:Denver, CO2", "#FF1493", "",COLLECT_LOOP_PING_DELAY_IN_SEC),

    Server("23.94.101.143", "O:Amsterdam", "#FF450F", "", COLLECT_LOOP_PING_DELAY_IN_SEC),   #1
    Server("23.94.53.39", "O:Atlanta, GA", "#00CED1", "", COLLECT_LOOP_PING_DELAY_IN_SEC),
    Server("72.18.215.113", "O:Kansas City, MO", "#800080", "",COLLECT_LOOP_PING_DELAY_IN_SEC),
    Server("107.175.219.234", "O:San Jose, CA", "#ADFF2F", "",COLLECT_LOOP_PING_DELAY_IN_SEC),

    Server("96.9.214.19", "O:Coventry", "#AF63FF", "", COLLECT_LOOP_PING_DELAY_IN_SEC),      #1
    Server("192.3.165.26", "O:Piscata, NJ", "#20B2AA", "", COLLECT_LOOP_PING_DELAY_IN_SEC),
    Server("192.227.193.172", "O:Dallas, TX", "#9370DB", "", COLLECT_LOOP_PING_DELAY_IN_SEC),
    Server("23.94.73.179", "O:Seattle, WA", "#FF69B4", "",COLLECT_LOOP_PING_DELAY_IN_SEC),

    #Server("20.223.230.52", "eu-north", "#FF0000", "", COLLECT_LOOP_PING_DELAY_IN_SEC),


    #Server("google.com", "", "#FF5733", "", COLLECT_LOOP_PING_DELAY_IN_SEC),


#FF6347 (Tomato)
#FF4500 (Orange Red)
#FF5733 (Vivid Orange)
#00FF00 (Lime Green)

#3366FF (Royal Blue)
#4169E1 (Royal Blue)
#800080 (Purple)
#9370DB (Medium Purple)

#008080 (Teal)
#00FFFF (Cyan)
#00CED1 (Dark Turquoise)
#20B2AA (Light Sea Green)

#FFD700 (Gold)
#FF1493 (Deep Pink)
#ADFF2F (Green Yellow)
#FF69B4 (Hot Pink)


]


class LiveGraph(QtWidgets.QWidget):
    def __init__(self):
        self.collect_loop_time_since_last_ping_in_sec = 0.0

        super().__init__()
        # Set up the window
        self.setWindowTitle('StatMonitor')
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: black;")

        # Create a vertical splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(splitter)



        # Set up the Ping line graph
        self.ping_plot = pg.PlotWidget(title="Ping (ms)")
        self.ping_plot_y_max = 0
        self.ping_plot.setAxisItems({'bottom': TimeAxisItem(orientation='bottom')})
        legend = self.ping_plot.addLegend()
        self.setColumnCount(legend, 4)
        #brush = QtGui.QBrush(
        #    QtGui.QColor(50, 50, 50, 100))  # RGBA: (0, 0, 0) is black, 100 is the alpha (transparency) value
        #legend.setBrush(brush)
        for server in SERVERS:
            server.curve = self.ping_plot.plot(pen=pg.mkPen(server.color), name=server.description)
        splitter.addWidget(self.ping_plot)

        # Add two more plots vertically
        self.jitter_plot = pg.PlotWidget(title="Ping Variance (ms)")
        self.jitter_plot.setAxisItems({'bottom': TimeAxisItem(orientation='bottom')})
        for server in SERVERS:
            server.jitter_curve = self.jitter_plot.plot(pen=pg.mkPen(server.color), name=server.description)
        splitter.addWidget(self.jitter_plot)

        self.packetloss_plot = pg.PlotWidget(title="Packetloss (%)")
        self.packetloss_plot.setAxisItems({'bottom': TimeAxisItem(orientation='bottom')})
        self.packetloss_plot.setYRange(0, 101)
        for server in SERVERS:
            server.packetloss_curve = self.packetloss_plot.plot(pen=pg.mkPen(server.color), name=server.description)
        splitter.addWidget(self.packetloss_plot)

        # Set up the CPU bar graph
        self.cpu_bar_graph = pg.BarGraphItem(x=[], height=[], width=0.6, brush='g')
        self.cpu_plot = pg.PlotWidget(title="CPU Utilization per Core")
        self.cpu_plot.setYRange(0, 110)
        self.cpu_plot.showGrid(x=True, y=True)
        self.cpu_plot.addItem(self.cpu_bar_graph)
        splitter.addWidget(self.cpu_plot)

        splitter.setSizes([900, 500, 320, 300])

        # Data storage
        self.cpu_data = [] * psutil.cpu_count()

        # Timers for GUI updates
        self.cpu_timer = QtCore.QTimer()
        self.cpu_timer.timeout.connect(self.fast_ui_updates)
        self.cpu_timer.start(100)

        self.ping_timer = QtCore.QTimer()
        self.ping_timer.timeout.connect(self.update_graphs)
        self.ping_timer.start(2000)  # Update graphs every 2 seconds

        # Start background thread for data collection
        self.collect_cpu_util_thread = threading.Thread(target=self.collect_cpu_util_data)
        self.collect_cpu_util_thread.daemon = True
        self.collect_cpu_util_thread.start()

    def fast_ui_updates(self):
        # toggle visibility
        changed = False
        for server in SERVERS:
            if server.curve.isVisible() != server.jitter_curve.isVisible():
                server.jitter_curve.setVisible(server.curve.isVisible())
                server.packetloss_curve.setVisible(server.curve.isVisible())
                changed = True
        if changed:
            self.update_graphs()

        self.update_cpu_graph()

    def update_cpu_graph(self):
        if self.cpu_data:
            x = list(range(len(self.cpu_data)))
            height = self.cpu_data

            # Update bar colors based on CPU usage
            brushes = [QtGui.QColor(0, int(255 * (1 - p / 100)), 0) if p <= 50 else
                       QtGui.QColor(int(255 * (p / 100)), int(255 * (1 - p / 100)), 0) for p in height]

            self.cpu_bar_graph.setOpts(x=x, height=height, brushes=brushes)

    def update_graphs(self):
        # Set the X axis ranges to the last 30 minutes (if there is enough data) or next 30 minutes (if there is not)
        x_data = []
        for server in SERVERS:
            if server.ping_data:
                if len(x_data) == 0:
                    x_data = server.time_data
                server.curve.setData(x=server.time_data, y=server.ping_data)
            if server.jitter_data:
                server.jitter_curve.setData(x=server.time_data, y=server.jitter_data)
            if server.loss_data:
                server.packetloss_curve.setData(x=server.time_data, y=server.loss_data)
        if len(x_data) > 0:
            self.ping_plot.setXRange(x_data[0], x_data[0] + 1800)
            self.jitter_plot.setXRange(x_data[0], x_data[0] + 1800)
            self.packetloss_plot.setXRange(x_data[0], x_data[0] + 1800)

        ###### PING PLOT ######
        # Adjust Y maximum depending on what graphs are visible
        ping_plot_y_axis_max = 0
        for server in SERVERS:
            if server.curve is not None and server.curve.isVisible() and len(server.ping_data) > 0:
                local_max = max(server.ping_data)
                if local_max > ping_plot_y_axis_max:
                    ping_plot_y_axis_max = local_max
        self.ping_plot.setYRange(0, ping_plot_y_axis_max + 10)

        ###### JITTER PLOT ######
        # Adjust Y maximum depending on what graphs are visible
        jitter_plot_y_axis_max = 22
        for server in SERVERS:
            if server.jitter_curve is not None and server.jitter_curve.isVisible() and len(server.jitter_data) > 0:
                local_max = max(server.jitter_data)
                if local_max > jitter_plot_y_axis_max:
                    jitter_plot_y_axis_max = local_max
        self.jitter_plot.setYRange(0, jitter_plot_y_axis_max + 3)


    def setColumnCount(self, legend, columnCount):
        def _addItemToLayout(legend, sample, label):
            col = legend.layout.columnCount()
            row = legend.layout.rowCount()
            if row:
                row -= 1
            nCol = legend.columnCount * 2
            # FIRST ROW FULL
            if col == nCol:
                for col in range(0, nCol, 2):
                    # FIND RIGHT COLUMN
                    if not legend.layout.itemAt(row, col):
                        break
                if col + 2 == nCol:
                    # MAKE NEW ROW
                    col = 0
                    row += 1
            legend.layout.addItem(sample, row, col)
            legend.layout.addItem(label, row, col + 1)

        legend.columnCount = columnCount
        legend.rowCount = int(len(legend.items) / columnCount)
        for i in range(legend.layout.count() - 1, -1, -1):
            legend.layout.removeAt(i)  # clear layout
        for sample, label in legend.items:
            _addItemToLayout(legend, sample, label)
        legend.updateSize()


    def collect_cpu_util_data(self):
        initialised = 0
        while True:
            if initialised != 1:
                initialised = 1
                self.cpu_data = psutil.cpu_percent(percpu=True)
            else:
                # update cpu core usage as a rolling average
                stability = 0.92
                new_cpu_data = psutil.cpu_percent(percpu=True)
                i = 0
                for core_usage_percentage in new_cpu_data:
                    self.cpu_data[i] = (stability * self.cpu_data[i]) + ((1 - stability) * core_usage_percentage)
                    i = i + 1
            time.sleep(COLLECT_LOOP_CPU_UTIL_DELAY_IN_SEC)


def handle_exit():
    print("Shutdown signal received")
    for server in SERVERS:
        server.writer.flush()


if __name__ == '__main__':
    safe_exit.register(handle_exit)
    app = QtWidgets.QApplication(sys.argv)
    live_graph = LiveGraph()
    live_graph.show()
    sys.exit(app.exec_())
