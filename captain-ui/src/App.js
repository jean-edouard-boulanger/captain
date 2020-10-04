import React, {useEffect, useState} from 'react';
import {
  Container,
  IconButton,
  AppBar,
  Toolbar,
  Grid,
  Collapse,
  Snackbar,
  Button,
  Typography
} from '@material-ui/core'
import MuiAlert from '@material-ui/lab/Alert';
import ClearIcon from '@material-ui/icons/Clear';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import socketIOClient from 'socket.io-client'

import StartDownload from './StartDownload';
import DownloadsTable from "./DownloadsTable";

import './App.css';


const SIO_ENDPOINT = "http://127.0.0.1:3001"


function Alert(props) {
  return <MuiAlert elevation={6} variant="filled" {...props} />;
}


function makeController(socket) {
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
    removeDownload: (handle) => {
      socket.emit("remove_download", {"handle": handle})
    },
    startDownload: (data) => {
      const makeAuth = () => {
        if(data.authMode === "none" || data.authMode === null)
        {
          return null;
        }
        let auth = {};
        auth[data.authMode] = data.credentials;
        return auth;
      }
      socket.emit("start_download", {
        remoteFileUrl: data.remoteFileUrl,
        localDir: data.localDir,
        auth: makeAuth()
      });
    }
  }
}

function App() {
  const [socket, setSocket] = useState(null);
  const [controller, setController] = useState(null);
  const [settings, setSettings] = useState(null);
  const [downloads, setDownloads] = useState([]);
  const [displayNewTaskForm, setDisplayNewTaskForm] = useState(false);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    setSocket(socketIOClient(SIO_ENDPOINT));
  }, []);

  useEffect(() => {
    if(socket === null) { return; }
    setController(makeController(socket));
  }, [socket])

  useEffect(() => {
    if(socket === null) { return; }
    socket.on("recap", data => {
      setSettings(data.settings);
      setDownloads(data.downloads.map(entry => {
        return {
          handle: entry.handle,
          payload: entry
        };
      }));
    });
    socket.on("download_event", data => {
      if(data.event_type === "GENERAL_NOTIFICATION") {
        setNotification({
          message: data.payload.message,
          severity: data.payload.severity
        });
        return;
      }
      if(data.event_type === "DOWNLOAD_ERRORED") {
        setNotification({
          message: data.payload.state.error_info.message,
          severity: "error"
        })
      }
      setDownloads(current => {
        const newDownloads = [...current];
        let existing = false;
        newDownloads.forEach(entry => {
          if (entry.handle === data.payload.handle) {
            entry.payload = data.payload;
            existing = true;
          }
        });
        if(!existing) {
          newDownloads.push({
            handle: data.payload.handle,
            payload: data.payload
          })
        }
        return newDownloads;
      });
    });
  }, [socket]);

  return (
    <React.Fragment>
      <AppBar title='Captain' color='primary'>
        <Toolbar>
          <Typography type='title' color='inherit'>
            Captain
          </Typography>
        </Toolbar>
      </AppBar>
      <Toolbar />
      <Toolbar />
      <Container maxWidth='lg'>
        <Collapse in={!displayNewTaskForm}>
          <Grid item xs={12}>
            <Button variant="contained"
                    startIcon={<AddCircleIcon />}
                    onClick={() => setDisplayNewTaskForm(true)} >
              New Task
            </Button>
          </Grid>
        </Collapse>
        <Collapse in={displayNewTaskForm}>
          <Grid item xs={12}>
            <StartDownload onStart={(data) => {
                             setDisplayNewTaskForm(false);
                             controller.startDownload(data);
                           }}
                           onCancel={() => setDisplayNewTaskForm(false)}
                           settings={settings} />
          </Grid>
        </Collapse>
        <Grid item xs={12}>
          <DownloadsTable downloads={downloads}
                          controller={controller}
                          settings={settings} />
        </Grid>
      </Container>
      <Snackbar anchorOrigin={{vertical: 'bottom', horizontal: 'left'}}
                open={notification !== null}
                onClose={() => setNotification(null)}
                autoHideDuration={(notification ?? {}).autoHideDuration}
                action={
                  <IconButton size="small" aria-label="close" color="inherit" >
                    <ClearIcon fontSize="small" />
                  </IconButton>
                }>
        <Alert severity={(notification ?? {}).severity || "info"} >
          {(notification ?? {}).message || ""}
        </Alert>
      </Snackbar>
    </React.Fragment>
  );
}

export default App;
