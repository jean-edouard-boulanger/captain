import {
  Chip, Divider,
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
import DeleteForeverIcon from '@material-ui/icons/DeleteForever';
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


const ACTION_MENU = {
  sections: [
    {
      items: [
        {
          text: 'Pause',
          visible: ({state}) => state.properties.can_be_paused,
          onClick: ({controller, handle}) => {
            controller.pauseDownload(handle);
          },
          Icon: PauseIcon
        },
        {
          text: 'Resume',
          visible: ({state}) => state.properties.can_be_resumed,
          onClick: ({controller, handle}) => {
            controller.resumeDownload(handle);
          },
          Icon: PlayArrowIcon
        },
        {
          text: 'Stop',
          visible: ({state}) => state.properties.can_be_stopped,
          onClick: ({controller, handle}) => {
            controller.stopDownload(handle);
          },
          Icon: StopIcon
        },
        {
          text: 'Retry',
          visible: ({state}) => state.properties.can_be_retried,
          onClick: ({controller, handle}) => {
            controller.retryDownload(handle);
          },
          Icon: ReplayIcon
        },
        {
          text: 'Start now',
          visible: ({state}) => state.properties.can_be_rescheduled,
          onClick: ({controller, handle}) => {
            controller.rescheduleDownload(handle, new Date());
          },
          Icon: PlayArrowIcon
        },
        {
          text: 'Reschedule',
          visible: ({state}) => state.properties.can_be_rescheduled,
          onClick: ({controller, handle}) => {
            controller.rescheduleDownload(handle, new Date());
          },
          Icon: AccessAlarmIcon
        }
      ]
    },
    {
      items: [
        {
          text: 'Download',
          visible: ({state}) => state.properties.can_be_downloaded,
          onClick: ({controller, handle}) => {
            const anchor = document.createElement('a');
            anchor.href = controller.getDownloadedFileUrl(handle);
            anchor.click();
          },
          Icon: GetAppIcon
        }
      ]
    },
    {
      items: [
        {
          text: 'Remove',
          visible: ({state}) => state.properties.is_final,
          onClick: ({controller, handle}) => {
            controller.removeDownload({handle, deleteFile: false});
          },
          Icon: ClearIcon
        },
        {
          text: 'Remove with data',
          visible: ({state}) => {
            return state.properties.is_final
              && state.file_location !== null;
          },
          onClick: ({controller, handle}) => {
            controller.removeDownload({handle, deleteFile: true});
          },
          Icon: DeleteForeverIcon
        },
      ]
    }
  ]
}

function getActionMenuSections({ entry, controller }) {
  const handle = entry.handle;
  const state = entry.state;
  const sections = []
  ACTION_MENU.sections.forEach((section) => {
    const items = section.items.filter((item) => {
      return item.visible({ state });
    });
    if(items.length > 0) {
      sections.push(items);
    }
  });
  return sections;
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
                      getActionMenuSections({ entry: payload, controller }).map((items) => {
                        return items.map((item) => {
                          const Icon = item.Icon;
                          return (
                              <MenuItem
                                onClick={() => {
                                  closeActionMenu();
                                  item.onClick({
                                    controller,
                                    handle: payload.handle
                                  });
                                }}
                              >
                                <ListItemIcon>
                                  <Icon fontSize="small"/>
                                </ListItemIcon>
                                <Typography variant="inherit">{item.text}</Typography>
                              </MenuItem>
                            )
                        }).concat([<Divider />])
                      })
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
