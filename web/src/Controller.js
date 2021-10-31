import {v4 as uuidv4} from "uuid";


export function makeController({endpoint, socket}) {
  const m_contexts = {};

  const handleRpcResponse = (payload) => {
    const messageId = payload.message_id;
    const context = m_contexts[messageId];
    if(context === undefined) {
      return;
    }
    delete m_contexts[messageId]
    if(payload.error !== null) {
      context.reject(payload.error);
    }
    else {
      context.resolve(payload.response);
    }
  };

  const handleRpcRequest = (request, settings) => {
    const messageId = uuidv4();
    settings = settings || {}
    let context = {messageId, request, resolve: null, reject: null};
    const promise = new Promise((resolve, reject) => {
      context.resolve = resolve;
      context.reject = reject;
    });
    m_contexts[messageId] = context;
    const payload = {
      "request": request,
      "message_id": messageId
    }
    socket.emit("rpc_request", payload);
    if(settings.timeout !== undefined) {
      const timeout = settings.timeout
      setTimeout(() => {
        handleRpcResponse({
          messageId: messageId,
          error: `request timed out after ${timeout} seconds`
        }, timeout * 1000);
      });
    }
    return promise;
  }

  socket.on("rpc_response", handleRpcResponse);

  return {
    pauseDownload: (handle) => {
      socket.emit("pause_download", {"handle": handle})
    },
    resumeDownload: (handle) => {
      socket.emit("resume_download", {"handle": handle})
    },
    stopDownload: (handle) => {
      socket.emit("stop_download", {"handle": handle})
    },
    retryDownload: (handle) => {
      socket.emit("retry_download", {"handle": handle})
    },
    rescheduleDownload: (handle, startAt) => {
      socket.emit("reschedule_download", {
        "handle": handle,
        "start_at": startAt.toISOString()
      })
    },
    removeDownload: ({handle, deleteFile}) => {
      socket.emit("remove_download", {
        "handle": handle,
        "delete_file": deleteFile ?? false
      });
    },
    startDownload: (data) => {
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
      const makeStartAt = () => {
        if(data.schedule === null) {
          return null;
        }
        return data.schedule.toISOString()
      };
      socket.emit("start_download", {
        remote_file_url: download.remoteFileUrl,
        download_dir: download.downloadDir,
        start_at: makeStartAt(),
        auth_method: makeAuth()
      });
    },
    validateDirectory: (directory) => {
      return handleRpcRequest({
        validate_download_directory: {
          directory
        }
      })
    },
    getDownloadedFileUrl: (downloadHandle) => {
      return `http://${endpoint}/download/${downloadHandle}`
    }
  }
}
