import datetime
import os
import sys
import psutil
import threading
import safe_exit
from PyQt5 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
import time
from Server import Server

COLLECT_LOOP_CPU_UTIL_DELAY_IN_SEC = 0.1
COLLECT_LOOP_PING_DELAY_IN_SEC = 5.0
PING_PLOT_ELEMENT_COUNT = 400
SERVERS = []

def format_time(seconds):
    if seconds > 0:
        return datetime.datetime.fromtimestamp(seconds).strftime('%H:%M:%S')
    else:
        return str(seconds)


class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [format_time(value) for value in values]


# Validates whether a line follows the format: STRING;STRING;STRING;Number.
def is_valid_server_entry(line):

    parts = line.strip().split(';')
    if len(parts) != 4:
        return False
    if not all(isinstance(part, str) for part in parts[:-1]):
        return False
    if not parts[-1].isdigit():
        return False
    return True


def add_server(line):
    print(f"Adding server: {line}")
    parts = line.strip().split(';')
    SERVERS.append(Server(parts[0], parts[1], parts[2], "", int(parts[3]), PING_PLOT_ELEMENT_COUNT))


def set_default_servers():
    default_servers = [
        "google.com;google.com;#FF0000;5",
    ]
    with open('servers.txt', 'w') as f:
        for server in default_servers:
            f.write(server + '\n')
    print("Default servers set.")


def process_servers_file():
    try:
        if os.path.exists('servers.txt'):
            with open('servers.txt', 'r') as f:
                for line in f:
                    if is_valid_server_entry(line):
                        add_server(line)
                    else:
                        print(f"Invalid server entry: {line}")
        else:
            set_default_servers()
    except Exception as e:
        print(f"Encountered an error: {e}")
        set_default_servers()


class LiveGraph(QtWidgets.QWidget):
    def __init__(self):
        process_servers_file()
        super().__init__()
        self.setWindowTitle('StatMonitor')
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: black;")

        # Create a vertical splitter to attach all graphs to
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addWidget(splitter)

        # Set up the Ping line graph
        self.ping_plot = pg.PlotWidget(title="Ping (ms)")
        self.ping_plot_y_max = 0
        self.ping_plot.setAxisItems({'bottom': TimeAxisItem(orientation='bottom')})
        legend = self.ping_plot.addLegend()
        self.setColumnCount(legend, 4)
        # Add the ping curves to the ping plot
        for server in SERVERS:
            server.curve = self.ping_plot.plot(pen=pg.mkPen(server.color), name=server.description)
        splitter.addWidget(self.ping_plot)

        # Add the jitter plot
        self.jitter_plot = pg.PlotWidget(title="Ping Variance (ms)")
        self.jitter_plot.setAxisItems({'bottom': TimeAxisItem(orientation='bottom')})
        for server in SERVERS:
            server.jitter_curve = self.jitter_plot.plot(pen=pg.mkPen(server.color), name=server.description)
        splitter.addWidget(self.jitter_plot)

        # Add the packetloss plot
        self.packetloss_plot = pg.PlotWidget(title="Packetloss (%)")
        self.packetloss_plot.setAxisItems({'bottom': TimeAxisItem(orientation='bottom')})
        self.packetloss_plot.setYRange(0, 101)
        for server in SERVERS:
            server.packetloss_curve = self.packetloss_plot.plot(pen=pg.mkPen(server.color), name=server.description)
        splitter.addWidget(self.packetloss_plot)

        # Add the cpu utilization plot
        self.cpu_bar_graph = pg.BarGraphItem(x=[], height=[], width=0.6, brush='g')
        self.cpu_plot = pg.PlotWidget(title="CPU Utilization per Core")
        self.cpu_plot.setYRange(0, 110)
        self.cpu_plot.showGrid(x=True, y=True)
        self.cpu_plot.addItem(self.cpu_bar_graph)
        splitter.addWidget(self.cpu_plot)

        # Set the default Sizing for the different plots attached to the splitter
        splitter.setSizes([900, 500, 320, 300])

        # Data storage
        self.cpu_data = [] * psutil.cpu_count()

        # 10 fps updates for fast updates to the ui like the rolling average of the cpu utilization
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
        self.update_cpu_graph()

        # toggle visibility
        changed = False
        for server in SERVERS:
            if server.curve.isVisible() != server.jitter_curve.isVisible():
                server.jitter_curve.setVisible(server.curve.isVisible())
                server.packetloss_curve.setVisible(server.curve.isVisible())
                changed = True
        if changed:
            self.update_graphs()

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
            timestamp = 0.0
            if len(x_data) < PING_PLOT_ELEMENT_COUNT:
                timestamp = x_data[0] + 1600
            else:
                timestamp = x_data[len(x_data) - 1]
            self.ping_plot.setXRange(x_data[0], timestamp)
            self.jitter_plot.setXRange(x_data[0], timestamp)
            self.packetloss_plot.setXRange(x_data[0], timestamp)

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
    #sys.exit()


if __name__ == '__main__':
    safe_exit.register(handle_exit)
    app = QtWidgets.QApplication(sys.argv)
    live_graph = LiveGraph()
    live_graph.show()
    sys.exit(app.exec_())
