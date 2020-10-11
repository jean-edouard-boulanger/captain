import React, {useState} from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Box,
  Button
} from "@material-ui/core";
import DateFnsUtils from '@date-io/date-fns';
import {
  MuiPickersUtilsProvider,
  KeyboardTimePicker,
  KeyboardDatePicker,
} from '@material-ui/pickers';


export default function ScheduleDialog({open, onSchedule, onClose}) {
  const [selectedDate, setSelectedDate] = useState(new Date());

  const handleDateChange = (date) => {
    setSelectedDate(date)
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <MuiPickersUtilsProvider utils={DateFnsUtils}>
        <DialogTitle>When should this download start?</DialogTitle>
        <DialogContent>
          <Box display="flex">
            <Box mr={2}>
              <KeyboardDatePicker
                disableToolbar
                variant="inline"
                format="MM/dd/yyyy"
                margin="normal"
                label="Date"
                onChange={handleDateChange}
                value={selectedDate} />
            </Box>
            <Box>
              <KeyboardTimePicker
                margin="normal"
                id="time-picker"
                label="Time picker"
                onChange={handleDateChange}
                value={selectedDate} />
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {onSchedule(selectedDate); onClose()}}>
            Schedule
          </Button>
          <Button onClick={() => onClose()}>
            Cancel
          </Button>
        </DialogActions>
      </MuiPickersUtilsProvider>
    </Dialog>
  );
}