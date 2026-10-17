(function () {
  var tracker = document.querySelector('[data-putt-tracker]');
  if (!tracker) return;

  var form = tracker.closest('form');
  var scoreInput = form.querySelector('#score');
  var manualEntry = form.querySelector('.manual-score-entry');
  var manualLabel = form.querySelector('[data-manual-label]');
  var trackerLabel = form.querySelector('[data-tracker-label]');
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

  manualEntry.hidden = true;
  manualLabel.hidden = true;
  trackerLabel.hidden = false;
  tracker.hidden = false;
  render();
})();
