import axios from "axios";


export class Controller {
  constructor(endpoint, socket) {
    this.endpoint = `http://${endpoint}`;
    this.socket = socket;
  }
  pauseDownload(handle) {
    this.socket.emit("pause_download", {handle})
  }
  resumeDownload(handle) {
    this.socket.emit("resume_download", {handle})
  }
  stopDownload(handle) {
    this.socket.emit("stop_download", {handle})
  }
  retryDownload(handle) {
    this.socket.emit("retry_download", {handle})
  }
  rescheduleDownload(handle, startAt) {
    this.socket.emit("reschedule_download", {
      handle,
      start_at: startAt.toISOString()
    })
  }
  removeDownload({handle, deleteFile}) {
    this.socket.emit("remove_download", {
      handle,
      delete_file: deleteFile ?? false
    });
  }
  startDownload(data) {
    const download = data.download;
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
    const makeStartAt = () => {
      if(data.schedule === null) {
        return null;
      }
      return data.schedule.toISOString()
    };
    this.socket.emit("start_download", {
      download_dir: download.downloadDir,
      start_at: makeStartAt(),
      download_method: makeDownloadMethod()
    });
  }
  async validateDownloadDirectory(directory) {
    const resource = `${this.endpoint}/api/v1/core/validate_download_directory`
    return (await axios.post(resource, {directory})).data;
  }
  getDownloadedFileUrl(downloadHandle) {
    return `${this.endpoint}/download/${downloadHandle}`
  }
}
