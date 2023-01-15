import React, {useEffect, useState, FunctionComponent} from 'react';
import {
  Alert,
  AlertColor,
  Container,
  IconButton,
  AppBar,
  Toolbar,
  Grid,
  Collapse,
  Snackbar,
  Button,
  Typography
} from '@mui/material'
import ClearIcon from '@mui/icons-material/Clear';
import AddCircleIcon from '@mui/icons-material/AddCircle';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';

import { StartDownload } from './StartDownload';
import { DownloadsTable } from "./DownloadsTable";
import { NotConnected } from "./NotConnected";

import { getServerEndpoint } from './endpoint';
import { AppSettings, ConnectState, DownloadTaskEntry } from "./domain";
import { Controller } from "./controller";

import './App.css';


interface AppProps {
  toggleDarkMode: () => void;
  darkMode: boolean
}

interface Notification {
  severity: string;
  message: string;
}

const App: FunctionComponent<AppProps> = ({toggleDarkMode, darkMode}) => {
  const [endpoint] = useState<string>(() => getServerEndpoint());
  const [controller, setController] = useState<Controller | null>(null);
  const [connectState, setConnectState] = useState<ConnectState>(ConnectState.Disconnect);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [downloads, setDownloads] = useState<Array<DownloadTaskEntry>>([]);
  const [displayNewTaskForm, setDisplayNewTaskForm] = useState<boolean>(false);
  const [notification, setNotification] = useState<Notification | null>(null);
  const ThemeIcon = darkMode ? LightModeIcon : DarkModeIcon;

  useEffect(() => {
    if(endpoint === null) { return; }
    setController(new Controller({
      endpoint,
      eventHandlers: {
        onConnectionStateChanged: (newState) => {
          setConnectState(newState);
        },
        onRecap: (data) => {
          setSettings(data.settings);
          setDownloads(data.downloads);
        },
        onNotification: ({payload}) => {
          setNotification({
            severity: payload.severity.toLowerCase(),
            message: payload.message,
          });
        },
        onDownloadTaskEvent: (event) => {
          if(event.event_type === "DOWNLOAD_ERRORED") {
            setNotification({
              severity: "error",
              message: event.payload.error_message,
            })
          }
          const payload = event.payload;
          setDownloads(current => {
            let exists = false;
            const newDownloads = [...current];
            for(let i = 0; i < current.length && !exists; ++i) {
              const entry = newDownloads[i];
              if(entry!.handle === payload.handle) {
                newDownloads[i] = payload;
                exists = true;
              }
            }
            if (!exists) {
              newDownloads.push(payload);
            }
            return newDownloads;
          });
        }
      }
    }));
  }, [endpoint]);

  const isConnected = () => {
    return connectState === ConnectState.Connect;
  };

  return (
    <React.Fragment>
      <AppBar title='Captain' color='primary'>
        <Toolbar>
          <Typography variant='inherit' color='inherit' sx={{ flexGrow: 1 }}>
            Captain
          </Typography>
          <IconButton size="large"
                      aria-label="account of current user"
                      aria-controls="menu-appbar"
                      aria-haspopup="true"
                      color="inherit"
                      onClick={toggleDarkMode} >
            <ThemeIcon />
          </IconButton>

        </Toolbar>
      </AppBar>
      <Toolbar />
      <Toolbar />
      <Container maxWidth='lg'>
      {
        (!isConnected()) &&
        <NotConnected currentState={connectState} />
      }
      {
        (isConnected()) &&
        <React.Fragment>
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
                               controller!.startDownload(data);
                             }}
                             onCancel={() => setDisplayNewTaskForm(false)}
                             settings={settings!}
                             controller={controller!} />
            </Grid>
          </Collapse>
          <Grid item xs={12}>
            <DownloadsTable downloads={downloads}
                            controller={controller!} />
          </Grid>
        </React.Fragment>
      }
      </Container>
      <Snackbar anchorOrigin={{vertical: 'bottom', horizontal: 'left'}}
                open={notification !== null}
                onClose={() => setNotification(null)}
                action={
                  <IconButton size="small" aria-label="close" color="inherit" >
                    <ClearIcon fontSize="small" />
                  </IconButton>
                }>
        <Alert elevation={6} severity={((notification ?? {}).severity || "info") as AlertColor}>
          {(notification ?? {}).message || ""}
        </Alert>
      </Snackbar>
    </React.Fragment>
  );
}

export default App;
