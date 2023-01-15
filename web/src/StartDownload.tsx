import React, {useEffect, useState, FunctionComponent} from 'react';
import {
  Button,
  Box,
  ListSubheader,
  Card,
  CardActions,
  CardContent,
  Divider,
  TextField,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid, IconButton
} from "@mui/material";
import {
  AppSettings,
  DownloadRequest,
  AuthMethodTypes,
  BasicCredentials,
  AuthMethod,
  DownloadMethod,
  YoutubeDownloadMethod,
  HttpDownloadMethod
} from "./domain"
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { Controller } from "./controller"
import { isBlank } from "./utils"
import {FileBrowserDialog} from "./FileBrowserDialog";

const CUSTOM_DOWNLOAD_DIR_SELECTION = "__SYS_CUSTOM__";
const BLANK_BASIC_AUTH: BasicCredentials = {method: "basic", username: "", password: ""};

function getDefaultDownloadLocation(settings: AppSettings): [string, string | undefined] {
  if(settings.download_directories.length === 0) {
    return [CUSTOM_DOWNLOAD_DIR_SELECTION, undefined];
  }
  const download_dir = settings.download_directories[0]!.directory;
  return [download_dir, download_dir]
}

function getBlankAuthMethod(authMethodType: AuthMethodTypes): AuthMethod | null {
  if(authMethodType === "basic") {
    return {...BLANK_BASIC_AUTH};
  }
  return null;
}

interface FormDataErrors {
  remoteFileUrl: boolean;
  downloadDir: boolean | string;
  username: boolean;
  password: boolean;
}

interface FormData {
  remoteFileUrl: string;
  saveTo: string;
  downloadDir: string;
  authMethod: AuthMethod | null;
}

function makeYoutubeDownloadMethod(formData: FormData): YoutubeDownloadMethod {
  return {
    method: "youtube",
    remote_file_url: formData.remoteFileUrl
  }
}

function makeHttpDownloadMethod(formData: FormData): HttpDownloadMethod {
  return {
    method: "http",
    remote_file_url: formData.remoteFileUrl,
    auth_method: formData.authMethod
  }
}

function makeDownloadMethod(formData: FormData): DownloadMethod {
  if (formData.remoteFileUrl.includes("youtube.")) {
    return makeYoutubeDownloadMethod(formData);
  }
  return makeHttpDownloadMethod(formData);
}

function makeDownloadRequest(formData: FormData): DownloadRequest {
  return {
    download_dir: formData.downloadDir,
    download_method: makeDownloadMethod(formData)
  }
}

interface StartDownloadProps {
  onStart: (request: DownloadRequest) => void;
  onCancel: () => void;
  settings: AppSettings;
  controller: Controller
}

export const StartDownload: FunctionComponent<StartDownloadProps> = ({onStart, onCancel, settings, controller}) => {
  const [remoteFileUrl, setRemoteFileUrl] = useState<string | undefined>();
  const [defaultSaveTo] = useState<string>(() => {
    return getDefaultDownloadLocation(settings)[0]
  })
  const [saveTo, setSaveTo] = useState<string>(defaultSaveTo);
  const [downloadDir, setDownloadDir] = useState<string | undefined>();
  const [authMethodType, setAuthMethodType] = useState<AuthMethodTypes>("none");
  const [authMethod, setAuthMethod] = useState<AuthMethod | null>(null);
  const [formErrors, setFormErrors] = useState<Partial<FormDataErrors>>({})
  const [browserOpened, setBrowserOpened] = useState<boolean>(false);

  useEffect(() => {
    if(isBlank(saveTo)) { return; }
    if(saveTo === CUSTOM_DOWNLOAD_DIR_SELECTION) {
      return;
    }
    setDownloadDir(saveTo);
  }, [saveTo]);

  useEffect(() => {
    setAuthMethod(getBlankAuthMethod(authMethodType))
  }, [authMethodType])

  const validateForm = async (data: Partial<FormData>) => {
    const errors: Partial<FormDataErrors> = {}
    if(isBlank(data.remoteFileUrl)) {
      errors.remoteFileUrl = true;
    }
    if(data.saveTo === CUSTOM_DOWNLOAD_DIR_SELECTION && isBlank(data.downloadDir)) {
      errors.downloadDir = true;
    }
    if(!isBlank(data.downloadDir)) {
      const {valid, reason} = await controller.validateDownloadDirectory(data.downloadDir as string);
      if(!valid) {
        errors.downloadDir = reason;
      }
    }
    if(data.authMethod?.method === "basic" && isBlank(data.authMethod?.username)) {
        errors.username = true
    }
    if(data.authMethod?.method === "basic" && isBlank(data.authMethod?.password)) {
        errors.password = true
    }
    return {
      errors,
      valid: Object.keys(errors).length === 0
    }
  }

  const getFormData = async () => {
    const downloadFormData = {
      remoteFileUrl,
      saveTo,
      downloadDir,
      authMethod
    };
    const validation = await validateForm(downloadFormData);
    const download = downloadFormData;
    return {
      download,
      ...validation
    };
  };

  const resetForm = () => {
    const [defaultSaveTo, defaultDownloadDir] = getDefaultDownloadLocation(settings)
    setRemoteFileUrl(undefined);
    setSaveTo(defaultSaveTo);
    setDownloadDir(defaultDownloadDir);
    setAuthMethodType("none");
    setAuthMethod(null);
    setFormErrors({});
  };

  const submitForm = async () => {
    const formData = await getFormData();
    if(!formData.valid) {
      setFormErrors(formData.errors);
    }
    else {
      resetForm();
      onStart(makeDownloadRequest(formData.download as FormData));
    }
  };

  useEffect(() => {
    setFormErrors({})
  }, [remoteFileUrl, saveTo, downloadDir, authMethodType, authMethod]);

  return (
    <Card>
      <CardContent>
        <Typography gutterBottom variant="h5" component="h2">
          New Task
        </Typography>
        <Grid container direction="column" spacing={2}>
          <Grid item>
            <Box m={1}>
            <TextField value={remoteFileUrl || ""}
                       variant="filled"
                       label="Remote file URL"
                       error={formErrors.remoteFileUrl !== undefined}
                       onChange={(e) => {setRemoteFileUrl(e.target.value)}}
                       fullWidth />
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex">
              <Box m={1}>
                <FormControl variant="filled" style={{minWidth: 200}}>
                  <InputLabel id="save-to-select-label">Save to</InputLabel>
                  <Select labelId="save-to-select-label"
                          value={saveTo}
                          onChange={(event) => {
                            setSaveTo(event.target.value)
                          }} >
                    {
                      (settings !== null) &&
                      [
                        <ListSubheader>Presets</ListSubheader>,
                        settings.download_directories.map((entry) => {
                          return (
                            <MenuItem value={entry.directory}>{entry.label}</MenuItem>
                          )
                        })
                      ]
                    }
                    <ListSubheader><Divider /></ListSubheader>,
                    <MenuItem value={CUSTOM_DOWNLOAD_DIR_SELECTION}>Custom</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box m={1} flexGrow={1}>
                <TextField label="Directory"
                           variant="filled"
                           value={downloadDir || ""}
                           error={formErrors.downloadDir !== undefined}
                           onChange={(e) => {setDownloadDir(e.target.value)}}
                           helperText={formErrors.downloadDir || ""}
                           disabled={saveTo !== CUSTOM_DOWNLOAD_DIR_SELECTION}
                           fullWidth
                           InputProps={(saveTo !== CUSTOM_DOWNLOAD_DIR_SELECTION) ? undefined : {
                             endAdornment:<IconButton onClick={() => setBrowserOpened(true)}><FolderOpenIcon /></IconButton>
                           }} />
              </Box>
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex">
              <Box m={1}>
                <FormControl variant="filled" style={{minWidth: 200}}>
                  <InputLabel id="auth-mode-select-label">Authentication</InputLabel>
                  <Select labelId="auth-mode-select-label"
                          value={authMethodType}
                          onChange={(e) => setAuthMethodType(e.target.value as AuthMethodTypes)}>
                    <MenuItem value="none">None</MenuItem>
                    <MenuItem value="basic">Simple</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box m={1} hidden={authMethodType !== "basic"}>
                <TextField label="Username"
                           variant="filled"
                           error={formErrors.username !== undefined}
                           onChange={(e) => {
                             const basicAuth = authMethod as BasicCredentials;
                             basicAuth.username = e.target.value;
                             setAuthMethod({...basicAuth});
                           }}
                           value={authMethod?.username || ""} />
              </Box>
              <Box m={1} hidden={authMethodType !== "basic"}>
                <TextField label="Password"
                           type="password"
                           variant="filled"
                           error={formErrors.password !== undefined}
                           onChange={(e) => {
                             const basicAuth = authMethod as BasicCredentials;
                             basicAuth.password = e.target.value;
                             setAuthMethod({...basicAuth});
                           }}
                           value={authMethod?.password || ""}/>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
      <CardActions>
        <Button size="small" onClick={submitForm}>
          Start
        </Button>
        <Button size="small" onClick={() => {resetForm(); onCancel()}}>
          Cancel
        </Button>
      </CardActions>
      <FileBrowserDialog open={browserOpened}
                         presets={settings.download_directories || []}
                         controller={controller}
                         onCancel={() => setBrowserOpened(false)}
                         onOpen={(selectedPath) => {
                           setBrowserOpened(false);
                           setDownloadDir(selectedPath);
                         }} />
    </Card>
  );
}
