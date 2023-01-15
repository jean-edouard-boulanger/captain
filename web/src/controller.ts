import axios from "axios";
import { Socket } from "socket.io-client";

export const ALL_AUTH_METHODS_TYPES = ["none", "basic"] as const
type AuthMethodTypesTuple = typeof ALL_AUTH_METHODS_TYPES
export type AuthMethodTypes = AuthMethodTypesTuple[number]

export interface AuthMethodBase<Method extends AuthMethodTypes> {
  method: Method
}

export interface BasicCredentials extends AuthMethodBase<"basic"> {
  username: string;
  password: string;
}

export type AuthMethod = BasicCredentials

export interface HttpDownloadMethod {
  method: "http";
  remote_file_url: string;
  auth_method: AuthMethod | null;
}

export interface YoutubeDownloadMethod {
  method: "youtube";
  remote_file_url: string;
}

export type DownloadMethod = HttpDownloadMethod | YoutubeDownloadMethod;

export interface DownloadRequest {
  download_dir: string;
  download_method: DownloadMethod
  start_at?: null;
}

export interface DownloadDirectory {
  directory: string;
  label: string
}

export interface AppSettings {
  download_directories: Array<DownloadDirectory>;
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
  startDownload(request: DownloadRequest) {
    /*const makeAuth = () => {
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
    }*/
    this.socket.emit("start_download", request);
  }
  async validateDownloadDirectory(directory: string) {
    const resource = `${this.endpoint}/api/v1/core/validate_download_directory`
    return (await axios.post(resource, {directory})).data;
  }
  getDownloadedFileUrl(handle: string) {
    return `${this.endpoint}/download/${handle}`
  }
}
