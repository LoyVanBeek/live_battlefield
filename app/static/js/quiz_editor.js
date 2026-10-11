/* Shared quiz question editor.
 *
 * Owns the question/answer state and its rendering (question text, answers,
 * per-answer bomb values, the correct-answer radio, warnings, JSON import/export).
 * Persistence (which endpoint, the enabled flag, the template name) stays in the
 * host page, so the GM settings page and the admin quiz library reuse one editor.
 *
 * Usage:
 *   const editor = createQuizEditor({
 *     listId: 'quiz-questions-list',        // required: container for question blocks
 *     totalId: 'quiz-total',                // optional: number input kept in sync
 *     warningId: 'quiz-warning-banner',     // optional: warning banner element
 *     addAnswerLabel: 'Add Answer',         // button label (translated by the host)
 *     toast: showToast,                     // optional: (message, type) => void
 *   });
 */
(function () {
    'use strict';

    function createQuizEditor(opts) {
        opts = opts || {};
        var questions = [];
        var list = opts.listId ? document.getElementById(opts.listId) : null;
        var totalInput = opts.totalId ? document.getElementById(opts.totalId) : null;
        var warningBanner = opts.warningId ? document.getElementById(opts.warningId) : null;
        var addAnswerLabel = opts.addAnswerLabel || 'Add Answer';
        var toast = typeof opts.toast === 'function' ? opts.toast : function () {};

        if (list) {
            list.addEventListener('change', onChange);
            list.addEventListener('click', onClick);
        }

        function esc(s) {
            return String(s == null ? '' : s)
                .replace(/&/g, '&amp;')
                .replace(/"/g, '&quot;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
        }

        // Max bombs a question can yield = the highest bomb value among its answers.
        function questionMaxYield(q) {
            if (!q.answers || q.answers.length === 0) return 0;
            return q.answers.reduce(function (m, a) {
                return Math.max(m, parseInt(a.bomb_value, 10) || 0);
            }, 0);
        }

        function render() {
            if (!list) return;
            list.innerHTML = questions.map(function (q, qi) {
                var answersHtml = (q.answers || []).map(function (a, ai) {
                    var val = parseInt(a.bomb_value, 10) || 0;
                    var bombColor = val > 0 ? '#4caf50' : '#888';
                    var bombWeight = val > 0 ? 'bold' : 'normal';
                    return (
                        '<div style="display:flex;gap:6px;align-items:center;margin-bottom:4px;padding-left:20px;">' +
                            '<input type="radio" name="correct-' + qi + '" data-role="correct" data-qi="' + qi + '" data-ai="' + ai + '" ' + (a.is_correct ? 'checked' : '') + '>' +
                            '<input type="text" data-role="answer-text" data-qi="' + qi + '" data-ai="' + ai + '" value="' + esc(a.answer_text) + '" placeholder="Answer" style="flex:1;padding:5px;font-size:12px;border-radius:3px;border:2px solid #0f3460;background:#1a1a2e;color:#eee;">' +
                            '<input type="number" id="ans-bombs-' + qi + '-' + ai + '" data-role="answer-bombs" data-qi="' + qi + '" data-ai="' + ai + '" min="0" step="1" value="' + val + '" aria-label="Bombs for answer ' + (ai + 1) + ' of question ' + (qi + 1) + '" style="width:60px;padding:4px;font-size:11px;border-radius:3px;border:2px solid #0f3460;background:#1a1a2e;color:#eee;">' +
                            '<span style="color:' + bombColor + ';font-size:12px;font-weight:' + bombWeight + ';">💣</span>' +
                            '<button class="btn btn-danger" data-action="remove-answer" data-qi="' + qi + '" data-ai="' + ai + '" style="padding:2px 6px;font-size:10px;">✕</button>' +
                        '</div>'
                    );
                }).join('');
                return (
                    '<div class="quiz-question" data-qi="' + qi + '" style="background:#0f3460;border-radius:6px;padding:12px;margin-bottom:10px;">' +
                        '<div style="display:flex;gap:6px;align-items:center;margin-bottom:8px;flex-wrap:wrap;">' +
                            '<span style="color:#888;font-size:12px;">Q' + (qi + 1) + '</span>' +
                            '<input type="text" data-role="question-text" data-qi="' + qi + '" value="' + esc(q.question_text) + '" placeholder="Question text" style="flex:1;padding:6px;font-size:13px;border-radius:4px;border:2px solid #0f3460;background:#1a1a2e;color:#eee;">' +
                            '<button class="btn btn-danger" data-action="remove-question" data-qi="' + qi + '" style="padding:4px 8px;font-size:11px;">✕</button>' +
                        '</div>' +
                        answersHtml +
                        '<button class="btn btn-primary" data-action="add-answer" data-qi="' + qi + '" style="padding:4px 10px;font-size:11px;margin-left:20px;margin-top:4px;">+ ' + esc(addAnswerLabel) + '</button>' +
                    '</div>'
                );
            }).join('');
            syncTotal();
            updateWarnings();
        }

        function onChange(e) {
            var t = e.target;
            var role = t.dataset ? t.dataset.role : null;
            if (!role) return;
            var qi = parseInt(t.dataset.qi, 10);
            var ai = parseInt(t.dataset.ai, 10);
            var q = questions[qi];
            if (!q) return;
            if (role === 'question-text') {
                q.question_text = t.value;
            } else if (role === 'answer-text') {
                if (q.answers[ai]) q.answers[ai].answer_text = t.value;
            } else if (role === 'correct') {
                q.answers.forEach(function (x, i) { x.is_correct = i === ai; });
                updateWarnings();
            } else if (role === 'answer-bombs') {
                setAnswerBombs(qi, ai, parseInt(t.value, 10) || 0);
            }
        }

        function onClick(e) {
            var btn = e.target.closest ? e.target.closest('button[data-action]') : null;
            if (!btn) return;
            var qi = parseInt(btn.dataset.qi, 10);
            var action = btn.dataset.action;
            if (action === 'remove-question') {
                removeQuestion(qi);
            } else if (action === 'add-answer') {
                addAnswer(qi);
            } else if (action === 'remove-answer') {
                removeAnswer(qi, parseInt(btn.dataset.ai, 10));
            }
        }

        // Per-answer bomb editing: the value lives on that single answer only.
        // Correctness is controlled by the radio and never changes from here.
        function setAnswerBombs(qi, ai, value) {
            var q = questions[qi];
            if (!q || !q.answers || !q.answers[ai]) return;
            q.answers[ai].bomb_value = value;
            render();
        }

        // Total bomb budget = sum of what each question can yield (its max answer).
        function syncTotal() {
            if (!totalInput) return;
            totalInput.value = questions.reduce(function (s, q) {
                return s + questionMaxYield(q);
            }, 0);
        }

        // Spread the total bomb budget evenly over the correct answer of every
        // question; wrong answers always end up with 0.
        function rebalance() {
            if (questions.length === 0) return;
            var total = totalInput ? (parseInt(totalInput.value, 10) || 0) : 0;
            questions.forEach(function (q) {
                if (!q.answers || q.answers.length === 0) return;
                if (!q.answers.some(function (a) { return a.is_correct; })) {
                    q.answers.reduce(function (best, a) {
                        return (parseInt(a.bomb_value, 10) || 0) > (parseInt(best.bomb_value, 10) || 0) ? a : best;
                    }, q.answers[0]).is_correct = true;
                }
            });
            var n = questions.length;
            if (total < n) {
                questions.forEach(function (q) {
                    var correct = q.answers.find(function (a) { return a.is_correct; });
                    if (!correct) return;
                    correct.bomb_value = 1;
                    q.answers.forEach(function (a) { if (a !== correct) a.bomb_value = 0; });
                });
                render();
                return;
            }
            var base = Math.floor(total / n);
            var rem = total % n;
            questions.forEach(function (q, qi) {
                var correct = q.answers.find(function (a) { return a.is_correct; });
                if (!correct) return;
                correct.bomb_value = base + (qi < rem ? 1 : 0);
                q.answers.forEach(function (a) { if (a !== correct) a.bomb_value = 0; });
            });
            render();
        }

        function addQuestion() {
            questions.push({
                question_text: '',
                bomb_value: 1,
                answers: [{ answer_text: '', bomb_value: 0, is_correct: true }],
            });
            rebalance();
        }

        function addAnswer(qi) {
            if (!questions[qi]) return;
            questions[qi].answers.push({ answer_text: '', bomb_value: 0, is_correct: false });
            render();
        }

        function removeQuestion(qi) {
            questions.splice(qi, 1);
            render();
        }

        function removeAnswer(qi, ai) {
            if (!questions[qi]) return;
            questions[qi].answers.splice(ai, 1);
            render();
        }

        // Flag questions that would leave players unable to earn bombs:
        // a question with no answers, or one where no answer is worth >= 1 bomb.
        function updateWarnings() {
            var problems = [];
            questions.forEach(function (q, qi) {
                if (!q.answers || q.answers.length === 0) {
                    problems.push('Question ' + (qi + 1) + ' has no answers.');
                } else if (questionMaxYield(q) < 1) {
                    problems.push('Question ' + (qi + 1) + ' has no answer worth at least 1 bomb.');
                }
            });
            if (warningBanner) {
                if (problems.length > 0) {
                    warningBanner.textContent = '⚠️ ' + problems.join(' ');
                    warningBanner.style.display = 'block';
                } else {
                    warningBanner.style.display = 'none';
                }
            }
            if (list) {
                Array.prototype.forEach.call(list.children, function (card, qi) {
                    var q = questions[qi];
                    var broken = !q || !q.answers || q.answers.length === 0 || questionMaxYield(q) < 1;
                    card.style.outline = broken ? '2px solid #ff5252' : '';
                });
            }
        }

        function getQuestions() {
            return questions;
        }

        function setQuestions(qs) {
            questions = Array.isArray(qs) ? qs : [];
            questions.forEach(function (q) {
                q.answers = q.answers || [];
                if (q.bomb_value == null) q.bomb_value = questionMaxYield(q);
                q.answers.forEach(function (a) {
                    a.bomb_value = parseInt(a.bomb_value, 10) || 0;
                });
            });
            render();
        }

        function toJSON() {
            return JSON.stringify(questions, null, 2);
        }

        function exportJSON(filename) {
            var blob = new Blob([toJSON()], { type: 'application/json' });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = filename || 'quiz_questions.json';
            a.click();
            URL.revokeObjectURL(url);
            toast('Exported ' + questions.length + ' question(s)!', 'success');
        }

        function importFile(event) {
            var file = event.target.files[0];
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function (e) {
                try {
                    var imported = JSON.parse(e.target.result);
                    if (!Array.isArray(imported)) throw new Error('Not an array');
                    var fixed = 0;
                    var normalized = imported.map(function (q, i) {
                        if (!q.question_text || !Array.isArray(q.answers)) {
                            throw new Error('Invalid question at index ' + i);
                        }
                        if (q.answers.length === 0) {
                            throw new Error('Question at index ' + i + ' has no answers.');
                        }
                        q.answers.forEach(function (a) {
                            if (!a.answer_text) throw new Error('Invalid answer in question ' + i);
                            a.bomb_value = parseInt(a.bomb_value, 10) || 0;
                        });
                        // Exactly one correct answer: keep an explicit one, else the
                        // highest-yield answer, else the first.
                        if (!q.answers.some(function (a) { return a.is_correct; })) {
                            var yielding = null;
                            q.answers.forEach(function (a) {
                                if (a.bomb_value > (yielding ? yielding.bomb_value : 0)) yielding = a;
                            });
                            (yielding || q.answers[0]).is_correct = true;
                        }
                        // Every question must be able to yield at least 1 bomb.
                        if (questionMaxYield(q) < 1) {
                            var correct = q.answers.find(function (a) { return a.is_correct; }) || q.answers[0];
                            correct.bomb_value = 1;
                            fixed++;
                        }
                        q.bomb_value = questionMaxYield(q);
                        return q;
                    });
                    setQuestions(normalized);
                    var msg = 'Imported ' + questions.length + ' question(s)!';
                    if (fixed > 0) msg += ' (' + fixed + ' had no bomb-yielding answer, set to 1).';
                    toast(msg, 'success');
                } catch (err) {
                    toast('Import failed: ' + err.message, 'error');
                }
            };
            reader.readAsText(file);
            event.target.value = '';
        }

        return {
            getQuestions: getQuestions,
            setQuestions: setQuestions,
            render: render,
            syncTotal: syncTotal,
            rebalance: rebalance,
            addQuestion: addQuestion,
            addAnswer: addAnswer,
            removeQuestion: removeQuestion,
            removeAnswer: removeAnswer,
            setAnswerBombs: setAnswerBombs,
            updateWarnings: updateWarnings,
            questionMaxYield: questionMaxYield,
            toJSON: toJSON,
            exportJSON: exportJSON,
            importFile: importFile,
        };
    }

    window.createQuizEditor = createQuizEditor;
})();
