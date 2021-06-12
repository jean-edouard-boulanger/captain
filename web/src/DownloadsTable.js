import {
  Chip,
  IconButton,
  LinearProgress,
  ListItemIcon,
  Menu,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow, Typography
} from "@material-ui/core";
import AccessAlarmIcon from '@material-ui/icons/AccessAlarm';
import MoreVertIcon from "@material-ui/icons/MoreVert";
import PauseIcon from "@material-ui/icons/Pause";
import PlayArrowIcon from "@material-ui/icons/PlayArrow";
import StopIcon from "@material-ui/icons/Stop";
import ReplayIcon from "@material-ui/icons/Replay";
import ClearIcon from "@material-ui/icons/Clear";
import GetAppIcon from '@material-ui/icons/GetApp';
import React, {useState} from "react";
import ScheduleDialog from "./ScheduleDialog";
import {format as format_date} from 'date-fns';

import { getServerEndpoint } from './endpoint';


function convertBytes(bps)
{
  if(bps >= 1000000) { return [(bps / 1000000).toFixed(1), "MB"] }
  if(bps >= 1000) { return [(bps / 1000).toFixed(1), "KB"] }
  return [bps.toFixed(1), "B"]
}


function defaultMetadata()
{
  return {
    remote_file_name: null,
    remote_url: null,
    file_size: null,
    file_type: null,
  };
}


export function DownloadsTable(props) {
  const [actionMenu, setActionMenu] = useState(null);
  const [scheduleDialog, setScheduleDialog] = useState(null);

  const {
    downloads,
    controller
  } = props;

  const isActionMenuOpen = (handle) => {
    return actionMenu !== null && actionMenu.handle === handle;
  }

  const closeActionMenu = () => {
    setActionMenu(null);
  }

  return (
    <TableContainer>
      <Table aria-label='simple-table'>
        <TableHead>
          <TableRow>
            <TableCell>File name</TableCell>
            <TableCell style={{minWidth: 200}}>Progress</TableCell>
            <TableCell style={{minWidth: 100}}>&nbsp;</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>&nbsp;</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
        {
          downloads.map(entry => {
            const payload = entry.payload;
            const handle = payload.handle;
            const state = payload.state;
            const metadata = state.metadata ?? defaultMetadata();
            const progress = (metadata.file_size === null)
              ? null
              : state.downloaded_bytes / metadata.file_size;
            return (
              <TableRow key={payload.handle}>
                <TableCell>{payload.user_request.properties.remote_file_name}</TableCell>
                <TableCell>
                  {(state.status === "SCHEDULED" && payload.user_request.start_at !== null) &&
                    `Will start on ${format_date(new Date(payload.user_request.start_at), 'MM/dd/yyyy hh:mm a')}`
                  }
                  {(progress !== null) &&
                    <LinearProgress variant="determinate"
                                    value={progress * 100} />
                  }
                </TableCell>
                <TableCell style={{minWidth: 50, maxWidth: 50}}>
                  {(state.status === "ACTIVE") &&
                    (state.current_rate !== null) && `${convertBytes(state.current_rate).join(" ")}/s`
                  }
                </TableCell>
                <TableCell>
                  <Chip variant="outlined" label={state.status} color={state.status === 'ERROR' ? 'secondary' : ''} />
                </TableCell>
                <TableCell>
                  <IconButton aria-label='actions'
                              aria-controls={`actions-menu-${handle}`}
                              aria-haspopup="true"
                              onClick={(event) => setActionMenu({anchor: event.currentTarget, handle})}>
                    <MoreVertIcon />
                  </IconButton>
                  <Menu id={`actions-menu-${handle}`}
                        anchorEl={(actionMenu ?? {anchor: null}).anchor}
                        keepMounted
                        open={isActionMenuOpen(handle)}
                        onClose={() => setActionMenu(null)} >
                    {
                      (state.properties.can_be_paused) &&
                      <MenuItem onClick={() => {closeActionMenu(); controller.pauseDownload(handle)}}>
                        <ListItemIcon>
                          <PauseIcon fontSize="small" />
                        </ListItemIcon>
                        <Typography variant="inherit">Pause</Typography>
                      </MenuItem>
                    }
                    {
                      (state.properties.can_be_resumed) &&
                      <MenuItem onClick={() => {closeActionMenu(); controller.resumeDownload(handle)}}>
                        <ListItemIcon>
                          <PlayArrowIcon fontSize="small" />
                        </ListItemIcon>
                        <Typography variant="inherit">Resume</Typography>
                      </MenuItem>
                    }
                    {
                      (state.properties.can_be_stopped) &&
                      <MenuItem onClick={() => {closeActionMenu(); controller.stopDownload(handle)}}>
                        <ListItemIcon>
                          <StopIcon fontSize="small" />
                        </ListItemIcon>
                        <Typography variant="inherit">Stop</Typography>
                      </MenuItem>
                    }
                    {
                      (state.properties.can_be_retried) &&
                      <MenuItem onClick={() => {closeActionMenu(); controller.retryDownload(handle)}}>
                        <ListItemIcon>
                          <ReplayIcon fontSize="small" />
                        </ListItemIcon>
                        <Typography variant="inherit">Retry</Typography>
                      </MenuItem>
                    }
                    {
                      (state.properties.can_be_rescheduled) &&
                      <MenuItem onClick={() => {
                        closeActionMenu();
                        controller.rescheduleDownload(handle, new Date())
                      }}>
                        <ListItemIcon>
                          <PlayArrowIcon fontSize="small" />
                        </ListItemIcon>
                        <Typography variant="inherit">Start now</Typography>
                      </MenuItem>
                    }
                    {
                      (state.properties.can_be_rescheduled) &&
                      <MenuItem onClick={() => {
                        closeActionMenu();
                        setScheduleDialog({
                          initialSchedule: Date.parse(payload.user_request.start_at),
                          onReschedule: ({schedule}) => {
                            controller.rescheduleDownload(handle, schedule);
                          }
                        })
                      }}>
                        <ListItemIcon>
                          <AccessAlarmIcon fontSize="small" />
                        </ListItemIcon>
                        <Typography variant="inherit">Reschedule</Typography>
                      </MenuItem>
                    }
                    {
                      (state.properties.is_final) &&
                      <MenuItem onClick={() => {closeActionMenu(); controller.removeDownload(handle)}}>
                        <ListItemIcon>
                          <ClearIcon fontSize="small" />
                        </ListItemIcon>
                        <Typography variant="inherit">Remove</Typography>
                      </MenuItem>
                    }
                    {
                      (state.properties.can_be_downloaded) &&
                      <MenuItem onClick={() => {
                        closeActionMenu();
                        const anchor = document.createElement('a');
                        anchor.href = `http://${getServerEndpoint()}/download/${handle}`;
                        anchor.click();
                      }}>
                        <ListItemIcon>
                          <GetAppIcon fontSize="small" />
                        </ListItemIcon>
                        <Typography variant="inherit">Download</Typography>
                      </MenuItem>
                    }
                  </Menu>
                </TableCell>
              </TableRow>
            );
          })
        }
        </TableBody>
      </Table>
      <ScheduleDialog open={scheduleDialog !== null}
                      initialSchedule={(scheduleDialog ?? {}).initialSchedule}
                      onClose={(schedule) => {
                        setScheduleDialog(null);
                        if(schedule !== null && schedule !== undefined) {
                          scheduleDialog.onReschedule({schedule});
                        }
                      }} />
    </TableContainer>
  )
}
