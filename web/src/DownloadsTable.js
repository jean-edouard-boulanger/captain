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


function formatBytes(bps)
{
  if(bps >= 1000000) { return [(bps / 1000000).toFixed(1), "MB"] }
  if(bps >= 1000) { return [(bps / 1000).toFixed(1), "KB"] }
  return [bps.toFixed(1), "B"]
}


const ACTIONS = {
  Resume: "r",
  Pause: "p",
  Stop: "S",
  Retry: "rt",
  Reschedule: "rs",
  Download: "d"
}


const ACTION_MENU = {
  sections: [
    {
      items: [
        {
          text: 'Pause',
          visible: ({valid_actions}) => valid_actions.includes(ACTIONS.Pause),
          onClick: ({controller, handle}) => {
            controller.pauseDownload(handle);
          },
          Icon: PauseIcon
        },
        {
          text: 'Resume',
          visible: ({valid_actions}) => valid_actions.includes(ACTIONS.Resume),
          onClick: ({controller, handle}) => {
            controller.resumeDownload(handle);
          },
          Icon: PlayArrowIcon
        },
        {
          text: 'Stop',
          visible: ({valid_actions}) => valid_actions.includes(ACTIONS.Stop),
          onClick: ({controller, handle}) => {
            controller.stopDownload(handle);
          },
          Icon: StopIcon
        },
        {
          text: 'Retry',
          visible: ({valid_actions}) => valid_actions.includes(ACTIONS.Retry),
          onClick: ({controller, handle}) => {
            controller.retryDownload(handle);
          },
          Icon: ReplayIcon
        },
        {
          text: 'Start now',
          visible: ({valid_actions}) => valid_actions.includes(ACTIONS.Reschedule),
          onClick: ({controller, handle}) => {
            controller.rescheduleDownload(handle, new Date());
          },
          Icon: PlayArrowIcon
        },
        {
          text: 'Reschedule',
          visible: ({valid_actions}) => valid_actions.includes(ACTIONS.Reschedule),
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
          visible: ({valid_actions}) => valid_actions.includes(ACTIONS.Download),
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
          visible: ({is_final}) => is_final,
          onClick: ({controller, handle}) => {
            controller.removeDownload({handle, deleteFile: false});
          },
          Icon: ClearIcon
        },
        {
          text: 'Remove with data',
          visible: ({is_final, valid_actions}) => is_final && valid_actions.includes(ACTIONS.Download),
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
  const sections = []
  ACTION_MENU.sections.forEach((section) => {
    const items = section.items.filter((item) => {
      return item.visible(entry);
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
            <TableCell>&nbsp;</TableCell>
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
            const downloadStatus = payload.status;
            return (
              <TableRow key={payload.handle}>
                <TableCell width={34}>
                  {(payload.download_method === "youtube") &&
                    <img src="youtube-logo64.png" width={34} alt="youtube" />
                  }
                </TableCell>
                <TableCell style={{
                  "text-overflow": "ellipsis",
                  "max-width": "200px",
                  "white-space": "nowrap",
                  "overflow": "hidden"
                }}>
                  {payload.file_name}
                </TableCell>
                <TableCell>
                  {(downloadStatus === "SCHEDULED" && payload.time_scheduled !== null) &&
                    `Will start on ${format_date(new Date(payload.time_scheduled), 'MM/dd/yyyy hh:mm a')}`
                  }
                  {(payload.progress_pc !== null) &&
                    <LinearProgress variant="determinate"
                                    value={payload.progress_pc * 100} />
                  }
                </TableCell>
                <TableCell style={{minWidth: 50, maxWidth: 50}}>
                  {(downloadStatus === "ACTIVE") &&
                    (payload.current_rate !== null) && `${formatBytes(payload.current_rate).join(" ")}/s`
                  }
                </TableCell>
                <TableCell>
                  <Chip variant="outlined" label={downloadStatus} color={downloadStatus === 'ERROR' ? 'secondary' : ''} />
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
                                  <item.Icon fontSize="small"/>
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
