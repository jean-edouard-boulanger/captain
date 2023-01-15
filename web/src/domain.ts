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

export const ALL_DOWNLOAD_METHOD_TYPES = ["http", "youtube"] as const
type DownloadMethodTypesTuple = typeof ALL_DOWNLOAD_METHOD_TYPES;
export type DownloadMethodTypes = DownloadMethodTypesTuple[number];

export interface DownloadMethodBase<Method extends DownloadMethodTypes> {
  method: Method
}

export interface HttpDownloadMethod extends DownloadMethodBase<"http">{
  remote_file_url: string;
  auth_method: AuthMethod | null;
}

export interface YoutubeDownloadMethod extends DownloadMethodBase<"youtube">{
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
  label: string;
}

export interface AppSettings {
  download_directories: Array<DownloadDirectory>;
}

export enum ConnectState {
  Connect = "connect",
  Connecting = "connecting",
  Disconnect = "disconnect",
  ConnectFailed = "connect_failed",
  Reconnect = "reconnect",
  Reconnecting = "reconnecting",
  ReconnectFailed = "reconnect_failed"
}

export interface DownloadEntry {
  handle: string;
  file_name: string;
  status: string;
  is_final: boolean;
  process_pc: number;
  current_rate: number;
  error_message: string;
  valid_actions: Array<string>;
  download_method: DownloadMethodTypes;
}

export interface RecapEvent {
  downloads: Array<DownloadEntry>;
  settings: AppSettings
}

export type DownloadTaskEventTypes =
  | "DOWNLOAD_SCHEDULED"
  | "DOWNLOAD_STARTED"
  | "PROGRESS_CHANGED"
  | "DOWNLOAD_COMPLETE"
  | "DOWNLOAD_STOPPED"
  | "DOWNLOAD_PAUSED"
  | "DOWNLOAD_RESUMED"
  | "DOWNLOAD_ERRORED"

export type DownloadEventTypes = DownloadTaskEventTypes | "GENERAL_NOTIFICATION"

export interface DownloadEventBase<EventType extends DownloadEventTypes, Payload> {
  event_type: EventType;
  payload: Payload
}

export interface GeneralNotificationPayload {
  severity: string;
  message: string;
}

export type GeneralNotificationEvent = DownloadEventBase<"GENERAL_NOTIFICATION", GeneralNotificationPayload>
export type DownloadTaskEvent = DownloadEventBase<DownloadTaskEventTypes, DownloadEntry>
export type DownloadEvent = GeneralNotificationEvent | DownloadTaskEvent
