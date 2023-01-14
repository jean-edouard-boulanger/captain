import axios from "axios";
import { Socket } from "socket.io-client";


interface Credentials {
  username: string | null;
  password: string | null;
}

interface Download {
  remoteFileUrl: string;
  saveTo: string;
  downloadDir: string;
  authMode: string;
  credentials: Credentials;
}

export class Controller {
  endpoint: string;
  socket: Socket

  constructor(endpoint: string, socket: Socket) {
    this.endpoint = endpoint;
    console.log(this.endpoint);
    this.socket = socket;
  }

  pauseDownload(handle: string) {
    this.socket.emit("pause_download", {handle})
  }
  resumeDownload(handle: string) {
    this.socket.emit("resume_download", {handle})
  }
  stopDownload(handle: string) {
    this.socket.emit("stop_download", {handle})
  }
  retryDownload(handle: string) {
    this.socket.emit("retry_download", {handle})
  }
  removeDownload({handle, deleteFile}: {handle: string, deleteFile: boolean}) {
    this.socket.emit("remove_download", {
      handle,
      delete_file: deleteFile ?? false
    });
  }
  startDownload(download: Download) {
    const makeAuth = () => {
      if(download.authMode === "none" || download.authMode === null)
      {
        return null;
      }
      return {
        method: download.authMode.toLowerCase(),
        ...download.credentials
      };
    };
    const makeDownloadMethod = () => {
      if(download.remoteFileUrl.includes("youtube.")) {
        return {
          method: "youtube",
          remote_file_url: download.remoteFileUrl
        }
      }
      else {
        return {
          method: "http",
          remote_file_url: download.remoteFileUrl,
          auth_method: makeAuth()
        }
      }
    }
    this.socket.emit("start_download", {
      download_dir: download.downloadDir,
      start_at: null,
      download_method: makeDownloadMethod()
    });
  }
  async validateDownloadDirectory(directory: string) {
    const resource = `${this.endpoint}/api/v1/core/validate_download_directory`
    return (await axios.post(resource, {directory})).data;
  }
  getDownloadedFileUrl(handle: string) {
    return `${this.endpoint}/download/${handle}`
  }
}
