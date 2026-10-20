(function () {
  var tracker = document.querySelector('[data-putt-tracker]');
  if (!tracker) return;

  var form = tracker.closest('form');
  var scoreInput = form.querySelector('#score');
  var manualEntry = form.querySelector('.manual-score-entry');
  var manualLabel = form.querySelector('[data-manual-label]');
  var trackerLabel = form.querySelector('[data-tracker-label]');
  var entryModeButton = form.querySelector('[data-entry-mode]');
  var preferenceStatus = form.querySelector('[data-entry-preference-status]');
  var preferenceKey = 'puttingleague.score-entry-mode.' + form.getAttribute('data-entry-user');
  var madeCount = 0;
  var results = [];
  var target = 20;

  var madeDisplay = tracker.querySelector('[data-putts-made]');
  var remainingDisplay = tracker.querySelector('[data-putts-remaining]');
  var totalDisplay = tracker.querySelector('[data-putts-total]');
  var progress = tracker.querySelector('[data-tracker-progress]');
  var progressBar = tracker.querySelector('[role="progressbar"]');
  var undoButton = tracker.querySelector('[data-putt-undo]');
  var submitButton = tracker.querySelector('[data-tracker-submit]');
  var status = tracker.querySelector('[data-tracker-status]');
  var resultButtons = tracker.querySelectorAll('[data-putt-result]');

  function render() {
    var attempts = results.length;
    var complete = attempts === target;

    madeDisplay.textContent = madeCount;
    remainingDisplay.textContent = target - attempts;
    totalDisplay.textContent = attempts + ' / ' + target + ' putts';
    progress.style.width = (attempts / target * 100) + '%';
    progressBar.setAttribute('aria-valuenow', attempts);
    undoButton.disabled = attempts === 0;
    submitButton.disabled = !complete;
    resultButtons.forEach(function (button) {
      button.disabled = complete;
    });

    if (complete) {
      status.textContent = 'Set complete. Ready to log.';
      scoreInput.value = madeCount;
    } else {
      status.textContent = attempts === 0 ? 'Tap a result for each putt.' : 'Keep going - ' + (target - attempts) + ' left.';
      scoreInput.value = '';
    }
  }

  function loadManualMode() {
    try {
      return window.localStorage.getItem(preferenceKey) === 'manual';
    } catch (error) {
      if (error.name !== 'SecurityError' && error.name !== 'QuotaExceededError') throw error;
      preferenceStatus.textContent = 'Browser storage is unavailable; using the putt tracker.';
      return false;
    }
  }

  function setEntryMode(manualMode) {
    manualEntry.hidden = !manualMode;
    tracker.hidden = manualMode;
    manualLabel.hidden = !manualMode;
    trackerLabel.hidden = manualMode;
    entryModeButton.textContent = manualMode ? 'Use putt tracker' : 'Enter score manually';
    entryModeButton.setAttribute('aria-pressed', manualMode);
    render();
  }

  function saveManualMode(manualMode) {
    try {
      window.localStorage.setItem(preferenceKey, manualMode ? 'manual' : 'tracker');
      preferenceStatus.textContent = '';
    } catch (error) {
      if (error.name !== 'SecurityError' && error.name !== 'QuotaExceededError') throw error;
      preferenceStatus.textContent = 'Browser storage is unavailable; this choice will not be remembered.';
    }
  }

  resultButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      if (results.length >= target) return;
      var made = button.getAttribute('data-putt-result') === 'make';
      results.push(made);
      if (made) madeCount += 1;
      render();
    });
  });

  undoButton.addEventListener('click', function () {
    var previousResult = results.pop();
    if (previousResult === undefined) return;
    if (previousResult) madeCount -= 1;
    render();
  });

  entryModeButton.hidden = false;
  setEntryMode(loadManualMode());

  entryModeButton.addEventListener('click', function () {
    var manualMode = manualEntry.hidden;
    setEntryMode(manualMode);
    saveManualMode(manualMode);
  });
})();
