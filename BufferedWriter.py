
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