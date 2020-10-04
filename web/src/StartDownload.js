import React, {useEffect, useState} from 'react';
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
  Grid
} from "@material-ui/core";


function isBlank(val) {
  return val === "" || val === null || val === undefined;
}


function defaultCredentials() {
  return {username: null, password: null};
}

export default function StartDownload({onStart, onCancel, settings}) {
  const [remoteFileUrl, setRemoteFileUrl] = useState(null);
  const [saveTo, setSaveTo] = useState("system-auto");
  const [localDir, setLocalDir] = useState(null);
  const [renameTo, setRenameTo] = useState(null);
  const [authMode, setAuthMode] = useState(null);
  const [credentials, setCredentials] = useState(defaultCredentials())
  const [formErrors, setFormErrors] = useState({})

  useEffect(() => {
    if(saveTo === null) { return; }
    if(saveTo === "system-auto" || saveTo === "system-custom") {
      setLocalDir(null);
      return;
    }
    setLocalDir(saveTo);
  }, [saveTo]);

  const validateForm = () => {
    const errors = {}
    if(isBlank(remoteFileUrl)) {
      errors.remoteFileUrl = true;
    }
    if(saveTo === "system-custom" && isBlank(localDir)) {
      errors.localDir = true;
    }
    if(authMode === "simple") {
      if(isBlank(credentials.username)) {
        errors.username = true
      }
      if(isBlank(credentials.password)) {
        errors.password = true
      }
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  const getFormData = () => {
    return {
      remoteFileUrl,
      localDir,
      renameTo,
      authMode,
      credentials
    };
  }

  const resetForm = () => {
    setRemoteFileUrl(null);
    setLocalDir(null);
    setAuthMode(null);
    setCredentials(defaultCredentials());
    setFormErrors({});
  }

  const submitForm = () => {
    if(validateForm()) {
      const formData = getFormData();
      resetForm();
      onStart(formData);
    }
  }

  console.log(settings);

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
                       label="Remote file URL"
                       error={formErrors.remoteFileUrl !== undefined}
                       onChange={(e) => {setRemoteFileUrl(e.target.value)}}
                       fullWidth />
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex">
              <Box m={1}>
                <FormControl style={{minWidth: 200}}>
                  <InputLabel id="save-to-select-label">Save to</InputLabel>
                  <Select labelId="save-to-select-label"
                          value={saveTo || "system-auto"}
                          onChange={(event) => {
                            setSaveTo(event.target.value)
                          }} >
                    <MenuItem value="system-auto">Automatic</MenuItem>
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
                    <MenuItem value="system-custom">Custom</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box m={1} flexGrow={1} hidden={saveTo === "system-auto"}>
                <TextField label="Directory"
                           value={localDir || ""}
                           error={formErrors.localDir !== undefined}
                           onChange={(e) => {setLocalDir(e.target.value)}}
                           disabled={saveTo !== "system-custom"}
                           fullWidth />
              </Box>
            </Box>
          </Grid>
          <Grid item>
            <Box m={1}>
              <TextField label="Rename file to"
                         value={renameTo || ""}
                         onChange={(e) => {setRenameTo(e.target.value)}}
                         fullWidth />
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex">
              <Box m={1}>
                <FormControl style={{minWidth: 200}}>
                  <InputLabel id="auth-mode-select-label">Authentication</InputLabel>
                  <Select labelId="auth-mode-select-label"
                          value={authMode || "none"}
                          onChange={(e) => setAuthMode(e.target.value)}>
                    <MenuItem value="none">None</MenuItem>
                    <MenuItem value="basic">Basic</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box m={1} hidden={authMode !== "basic"}>
                <TextField label="Username"
                           error={formErrors.username !== undefined}
                           onChange={(e) => {
                             credentials.username = e.target.value;
                             setCredentials({...credentials});
                           }}
                           value={credentials.username} />
              </Box>
              <Box m={1} hidden={authMode !== "basic"}>
                <TextField label="Password"
                           type="password"
                           error={formErrors.password !== undefined}
                           onChange={(e) => {
                             credentials.password = e.target.value;
                             setCredentials({...credentials});
                           }}
                           value={credentials.password}/>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
      <CardActions>
        <Button size="small" onClick={() => submitForm()}>
          Start
        </Button>
        <Button size="small" onClick={() => {resetForm(); onCancel()}}>
          Cancel
        </Button>
      </CardActions>
    </Card>
  );
}