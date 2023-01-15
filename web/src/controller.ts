import axios from "axios";
import socketIOClient, { Socket } from "socket.io-client";
import { ConnectState, DownloadRequest, RecapEvent, DownloadEvent, DownloadTaskEvent, GeneralNotificationEvent } from "./domain"

const noopHandler = () => {};

export interface EventHandlers {
  onConnectionStateChanged: (newState: ConnectState) => void;
  onRecap: (event: RecapEvent) => void;
  onDownloadTaskEvent: (event: DownloadTaskEvent) => void;
  onNotification: (event: GeneralNotificationEvent) => void;
}

const makeEventHandlers = (eventHandlers: Partial<EventHandlers> | undefined): EventHandlers => {
  eventHandlers = eventHandlers || {}
  return {
    onConnectionStateChanged: eventHandlers.onConnectionStateChanged || noopHandler,
    onRecap: eventHandlers.onRecap || noopHandler,
    onDownloadTaskEvent: eventHandlers.onDownloadTaskEvent || noopHandler,
    onNotification: eventHandlers.onNotification || noopHandler
  }
}

export interface ControllerProps {
  endpoint: string;
  eventHandlers?: Partial<EventHandlers>;
}

export class Controller {
  readonly #endpoint: string;
  #socket: Socket;
  readonly #eventHandlers: EventHandlers;

  constructor({endpoint, eventHandlers}: ControllerProps) {
    this.#endpoint = endpoint;
    this.#socket = socketIOClient(endpoint);
    this.#eventHandlers = makeEventHandlers(eventHandlers);
    this.#subscribe()
  }

  #subscribe() {
    const handlers = this.#eventHandlers;
    this.#socket.on("connect", () => { handlers.onConnectionStateChanged(ConnectState.Connect) });
    this.#socket.on("connecting", () => { handlers.onConnectionStateChanged(ConnectState.Connecting) });
    this.#socket.on("disconnect", () => { handlers.onConnectionStateChanged(ConnectState.Disconnect) });
    this.#socket.on("connect_failed", () => { handlers.onConnectionStateChanged(ConnectState.ConnectFailed) });
    this.#socket.on("reconnect", () => { handlers.onConnectionStateChanged(ConnectState.Reconnect) });
    this.#socket.on("reconnecting", () => { handlers.onConnectionStateChanged(ConnectState.Reconnecting) });
    this.#socket.on("reconnect_failed", () => { handlers.onConnectionStateChanged(ConnectState.ReconnectFailed) });
    this.#socket.on("recap", (event: RecapEvent) => { handlers.onRecap(event) })
    this.#socket.on("download_event", (event: DownloadEvent) => {
      if(event.event_type === "GENERAL_NOTIFICATION") {
        return handlers.onNotification(event);
      }
      return handlers.onDownloadTaskEvent(event);
    })
  }

  pauseDownload(handle: string) {
    this.#socket.emit("pause_download", {handle})
  }
  resumeDownload(handle: string) {
    this.#socket.emit("resume_download", {handle})
  }
  stopDownload(handle: string) {
    this.#socket.emit("stop_download", {handle})
  }
  retryDownload(handle: string) {
    this.#socket.emit("retry_download", {handle})
  }
  removeDownload({handle, deleteFile}: {handle: string, deleteFile: boolean}) {
    this.#socket.emit("remove_download", {
      handle,
      delete_file: deleteFile ?? false
    });
  }
  startDownload(request: DownloadRequest) {
    this.#socket.emit("start_download", request);
  }
  async validateDownloadDirectory(directory: string) {
    const resource = `${this.#endpoint}/api/v1/core/validate_download_directory`
    return (await axios.post(resource, {directory})).data;
  }
  getDownloadedFileUrl(handle: string) {
    return `${this.#endpoint}/download/${handle}`
  }
}
