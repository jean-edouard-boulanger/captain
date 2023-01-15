import React, {useState, FunctionComponent, useEffect} from 'react';
import {
  Box,
  Button,
  ListItemButton,
  Breadcrumbs,
  Dialog, DialogContent, Grid, List, ListItem, ListItemIcon, ListItemText, Stack, Link, DialogActions, Typography
} from '@mui/material'
import { DataGrid, GridRowsProp, GridColDef, GridEventListener } from '@mui/x-data-grid';
import FolderIcon from '@mui/icons-material/Folder';
import {DownloadDirectory} from "./domain";
import {Controller} from "./controller";


export interface FileBrowserProps {
  open: boolean
  presets: Array<DownloadDirectory>
  controller: Controller
  onCancel?: () => void;
  onOpen?: (path: string) => void;
}

const columns: GridColDef[] = [
  { field: 'name', headerName: 'Name', width: 400 },
  { field: 'kind', headerName: 'Kind', width: 150 },
];

export const FileBrowserDialog: FunctionComponent<FileBrowserProps> = (props) => {
  const {open, presets, controller, onOpen, onCancel} = props;
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [directoryChildren, setDirectoryChildren] = useState<GridRowsProp>([]);
  const [discoveryFailed, setDiscoveryFailed] = useState<boolean>(false);
  const selectedPathItems = selectedPath !== null ? selectedPath.split("/") : [];

  useEffect(() => {
    if(presets === null) { return; }
    setSelectedPath(presets[0]!.directory)
  }, [presets])

  useEffect(() => {
    const discoverDirectory = async () => {
      if(selectedPath === null) { return; }
      const payload = await controller.discoverDirectory(selectedPath)
      if(!payload.success) {
        setDirectoryChildren([]);
        setDiscoveryFailed(true);
        return;
      }
      setDirectoryChildren(payload.contents.map((entry, index) => {
        return {
          id: index,
          name: entry.name,
          kind: entry.kind === 'd' ? "Directory" : 'File'
        }
      }));
    }
    setDiscoveryFailed(false);
    discoverDirectory()
  }, [controller, selectedPath])

  const handleDirChildSelected: GridEventListener<'rowDoubleClick'> = (params) => {
    const row = params.row;
    if(row.kind === 'File') { return; }
    setSelectedPath(`${selectedPath}/${row.name}`)
  }

  const handleParentDirSelected = (componentIndex: number) => {
    const components = [];
    for(let i = 0; i <= componentIndex; ++i) {
      components.push(selectedPathItems[i]);
    }
    setSelectedPath(components.join("/"))
  }

  return (
    <Dialog open={open}
            fullWidth={true}
            maxWidth={"md"}>
      <DialogContent>
        <Grid container spacing={2}>
          <Grid item xs={4}>
            <Box sx={{height: "450px", width: '100%'}}>
              <List dense={true}>
                <ListItem>
                  <ListItemText>Presets</ListItemText>
                </ListItem>
                {
                  presets.map((preset) => {
                    return (
                      <ListItemButton selected={selectedPath === preset.directory}
                                      onClick={() => setSelectedPath(preset.directory)} >
                        <ListItemIcon>
                          <FolderIcon />
                        </ListItemIcon>
                        <ListItemText>{preset.label}</ListItemText>
                      </ListItemButton>
                    )
                  })
                }
              </List>
            </Box>
          </Grid>
          <Grid item xs={8}>
            <Stack spacing={2}>
              <Breadcrumbs>
                {
                  selectedPathItems.map((component, index) => {
                    if(index < selectedPathItems.length - 1) {
                      return (
                        <Link style={{ cursor: 'grab' }}
                              onClick={() => {handleParentDirSelected(index)}} >
                          {component}
                        </Link>
                      )
                    }
                    else {
                      return (
                        <Typography color="text.primary">{component}</Typography>
                      )
                    }
                  })
                }
              </Breadcrumbs>
              <div style={{ height: '450px', overflow: "auto" }}>
                <DataGrid rows={directoryChildren}
                          columns={columns}
                          density="compact"
                          hideFooter={directoryChildren.length <= 100}
                          onRowDoubleClick={handleDirChildSelected}
                          error={discoveryFailed} />
              </div>
            </Stack>
          </Grid>
        </Grid>
        <DialogActions>
          <Button onClick={onCancel}>Cancel</Button>
          <Button disabled={selectedPath === null} onClick={() => onOpen && onOpen(selectedPath!)}>Open</Button>
        </DialogActions>
      </DialogContent>
    </Dialog>
  )
}
