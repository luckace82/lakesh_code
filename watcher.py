from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from indexer import index_file

class Handler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            index_file(event.src_path)

if __name__ == '__main__':
    obs = Observer()
    obs.schedule(Handler(), path='.', recursive=True)
    obs.start()
    print("Watcher started. Monitoring for file changes...")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        obs.stop()
    obs.join()
