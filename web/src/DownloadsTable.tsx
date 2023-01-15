import {
  Chip,
  Divider,
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
  TableRow,
  Typography
} from "@mui/material";
import {SvgIcon} from "@mui/material";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import ReplayIcon from "@mui/icons-material/Replay";
import ClearIcon from "@mui/icons-material/Clear";
import GetAppIcon from '@mui/icons-material/GetApp';
import DeleteForeverIcon from '@mui/icons-material/DeleteForever';
import React, {useState, FunctionComponent} from 'react';
import {format as formatDate} from 'date-fns';
import {DownloadTaskEntry} from "./domain"
import {Controller} from "./controller"


function formatBytes(bps: number): [string, string]
{
  if(bps >= 1000000) { return [(bps / 1000000).toFixed(1), "MB"] }
  if(bps >= 1000) { return [(bps / 1000).toFixed(1), "KB"] }
  return [bps.toFixed(1), "B"]
}


enum Action {
  Resume= "r",
  Pause = "p",
  Stop = "S",
  Retry = "rt",
  Reschedule = "rs",
  Download = "d"
}


interface ActionMenuSectionItemProps {
  text: string;
  visible: ({valid_actions, is_final}: {valid_actions: Array<string>, is_final: boolean}) => boolean;
  onClick: ({controller, handle}: {controller: Controller, handle: string}) => void;
  Icon: typeof SvgIcon;
}

interface ActionMenuSectionProps {
  items: Array<ActionMenuSectionItemProps>;
}

interface ActionMenuProps {
  sections: Array<ActionMenuSectionProps>;
}

const ACTION_MENU: ActionMenuProps = {
  sections: [
    {
      items: [
        {
          text: 'Pause',
          visible: ({valid_actions}) => valid_actions.includes(Action.Pause),
          onClick: ({controller, handle}) => {
            controller.pauseDownload(handle);
          },
          Icon: PauseIcon
        },
        {
          text: 'Resume',
          visible: ({valid_actions}) => valid_actions.includes(Action.Resume),
          onClick: ({controller, handle}) => {
            controller.resumeDownload(handle);
          },
          Icon: PlayArrowIcon
        },
        {
          text: 'Stop',
          visible: ({valid_actions}) => valid_actions.includes(Action.Stop),
          onClick: ({controller, handle}) => {
            controller.stopDownload(handle);
          },
          Icon: StopIcon
        },
        {
          text: 'Retry',
          visible: ({valid_actions}) => valid_actions.includes(Action.Retry),
          onClick: ({controller, handle}) => {
            controller.retryDownload(handle);
          },
          Icon: ReplayIcon
        }
      ]
    },
    {
      items: [
        {
          text: 'Download',
          visible: ({valid_actions}) => valid_actions.includes(Action.Download),
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
          visible: ({is_final, valid_actions}) => is_final && valid_actions.includes(Action.Download),
          onClick: ({controller, handle}) => {
            controller.removeDownload({handle, deleteFile: true});
          },
          Icon: DeleteForeverIcon
        },
      ]
    }
  ]
}

function getActionMenuSections({ entry, controller }: { entry: any, controller: Controller }) {
  const sections: Array<Array<ActionMenuSectionItemProps>> = []
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

interface DownloadsTableProps {
  downloads: Array<DownloadTaskEntry>;
  controller: Controller;
}

interface ActionMenuAnchorProps {
  handle: string;
  anchor: EventTarget & HTMLButtonElement
}

export const DownloadsTable: FunctionComponent<DownloadsTableProps> = ({downloads, controller}) => {
  const [actionMenuAnchor, setActionMenuAnchor] = useState<ActionMenuAnchorProps | null>(null);

  const isActionMenuOpen = (handle: string) => {
    return actionMenuAnchor !== null && actionMenuAnchor.handle === handle;
  }

  const closeActionMenu = () => {
    setActionMenuAnchor(null);
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
          downloads.map(payload => {
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
                  "textOverflow": "ellipsis",
                  "maxWidth": "200px",
                  "whiteSpace": "nowrap",
                  "overflow": "hidden"
                }}>
                  {payload.file_name}
                </TableCell>
                <TableCell>
                  {(downloadStatus === "SCHEDULED" && payload.time_scheduled !== null) &&
                    `Will start on ${formatDate(new Date(payload.time_scheduled), 'MM/dd/yyyy hh:mm a')}`
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
                  <Chip variant="outlined" label={downloadStatus} color={downloadStatus === 'ERROR' ? 'error' : 'primary'} />
                </TableCell>
                <TableCell>
                  <IconButton aria-label='actions'
                              aria-controls={`actions-menu-${handle}`}
                              aria-haspopup="true"
                              onClick={(event) => setActionMenuAnchor({anchor: event.currentTarget, handle})}>
                    <MoreVertIcon />
                  </IconButton>
                  <Menu id={`actions-menu-${handle}`}
                        anchorEl={(actionMenuAnchor ?? {anchor: null}).anchor}
                        keepMounted
                        open={isActionMenuOpen(handle)}
                        onClose={() => setActionMenuAnchor(null)} >
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
    </TableContainer>
  )
}
