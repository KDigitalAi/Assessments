// API Configuration
const API_BASE_URL = 'http://127.0.0.1:8000/api';

// State
let currentAssessment = null;
let currentAttemptId = null;
let answers = {};
let timerInterval = null;
let timeRemaining = 0;
let currentQuestionIndex = 0;

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    loadAssessmentFromStorage();
});

async function autoStartAssessment() {
    try {
        console.log('🔄 No assessment data found. Auto-starting assessment...');
        
        // Show loading state
        document.getElementById('questionContainer').innerHTML = '<div class="loading">Loading assessment...</div>';
        
        // Step 1: Get available assessments
        const assessmentsResponse = await fetch(`${API_BASE_URL}/getAssessments`);
        if (!assessmentsResponse.ok) {
            throw new Error(`Failed to fetch assessments: HTTP ${assessmentsResponse.status}`);
        }
        
        const assessmentsData = await assessmentsResponse.json();
        if (!assessmentsData.success || !assessmentsData.assessments || assessmentsData.assessments.length === 0) {
            throw new Error('No assessments available. Please generate assessments first.');
        }
        
        // Step 2: Get the first available assessment
        const firstAssessment = assessmentsData.assessments[0];
        const assessmentId = firstAssessment.id;
        
        console.log(`✅ Found assessment: ${firstAssessment.skill_name} (ID: ${assessmentId})`);
        
        // Step 3: Fetch questions and create attempt
        const questionsResponse = await fetch(`${API_BASE_URL}/assessments/${assessmentId}/questions`);
        if (!questionsResponse.ok) {
            const errorData = await questionsResponse.json().catch(() => ({ detail: `HTTP ${questionsResponse.status}` }));
            throw new Error(errorData.detail || errorData.error || `Failed to fetch questions: HTTP ${questionsResponse.status}`);
        }
        
        const data = await questionsResponse.json();
        console.log('✅ Assessment data received:', data);
        
        // Validate response
        if (!data.success) {
            throw new Error(data.error || data.detail || 'Failed to start assessment');
        }
        
        if (!data.questions || data.questions.length === 0) {
            throw new Error('No questions found for this assessment');
        }
        
        // Store assessment data in localStorage
        const assessmentData = {
            assessment_id: data.assessment_id || assessmentId,
            attempt_id: data.attempt_id || null,
            title: data.title || firstAssessment.skill_name,
            questions: data.questions,
            duration_minutes: data.duration_minutes || 30,
            started_at: data.started_at || new Date().toISOString()
        };
        
        localStorage.setItem('currentAssessment', JSON.stringify(assessmentData));
        
        // Also store attempt_id separately for reliability
        if (data.attempt_id) {
            localStorage.setItem('attempt_id', data.attempt_id);
            console.log('✅ Attempt ID stored:', data.attempt_id);
        } else {
            console.warn('⚠️  No attempt_id returned from server');
            if (data.error) {
                console.error('Server error:', data.error);
            }
            if (data.warning) {
                console.warn('Server warning:', data.warning);
            }
            // Store warning in assessment data so it can be shown
            assessmentData.warning = data.warning || data.error || 'No attempt created. Submission may fail.';
        }
        
        // Load the assessment
        loadAssessmentFromStorage();
        
    } catch (error) {
        console.error('❌ Error auto-starting assessment:', error);
        showError(`Failed to auto-start assessment: ${error.message}. Please start an assessment from the dashboard.`);
        document.getElementById('questionContainer').innerHTML = '<div class="error-message">Failed to load assessment. Please go back to the dashboard and start an assessment.</div>';
    }
}

function loadAssessmentFromStorage() {
    try {
        const storedData = localStorage.getItem('currentAssessment');
        
        if (!storedData) {
            // Auto-start assessment if no data found
            autoStartAssessment();
            return;
        }

        currentAssessment = JSON.parse(storedData);
        
        if (!currentAssessment || !currentAssessment.questions || currentAssessment.questions.length === 0) {
            showError('Invalid assessment data. Please start a new assessment.');
            return;
        }

        // Initialize state
        currentAttemptId = currentAssessment.attempt_id || null;
        currentQuestionIndex = 0;
        answers = {};
        timeRemaining = (currentAssessment.duration_minutes || 30) * 60;
        
        // Store attempt_id separately for reliability
        if (currentAttemptId) {
            localStorage.setItem('attempt_id', currentAttemptId);
            console.log('✅ Attempt ID stored:', currentAttemptId);
        } else {
            // Try to get from separate localStorage key
            currentAttemptId = localStorage.getItem('attempt_id');
            if (currentAttemptId) {
                console.log('✅ Attempt ID retrieved from localStorage:', currentAttemptId);
            } else {
                // Check if there's a warning from the server
                if (currentAssessment.warning) {
                    console.warn('⚠️  Server warning:', currentAssessment.warning);
                    showError(currentAssessment.warning);
                } else {
                    console.error("❌ No attempt_id found. Submission will fail.");
                    console.error("   This usually means no user profile exists in the database.");
                    console.error("   Please ensure at least one profile exists in the 'profiles' table.");
                    showError('No active assessment attempt. Please ensure at least one user profile exists in the database.');
                }
                // Disable submit button if no attempt_id
                document.getElementById('btnSubmit').disabled = true;
                document.getElementById('btnSubmit').textContent = 'Cannot Submit - No Attempt Created';
                // Still allow viewing questions, but disable submission
                // Don't return - let questions display
            }
        }

        // Display assessment
        displayAssessment();
        startTimer();
        
        // Enable submit button
        document.getElementById('btnSubmit').disabled = false;
        
    } catch (error) {
        console.error('Error loading assessment:', error);
        showError('Failed to load assessment data: ' + error.message);
    }
}

function displayAssessment() {
    if (!currentAssessment) return;

    // Update header
    document.getElementById('assessmentTitle').textContent = currentAssessment.title || 'Assessment';
    document.getElementById('totalQuestions').textContent = currentAssessment.questions.length;

    // Display questions
    displayQuestions();
}

function displayQuestions() {
    const container = document.getElementById('questionContainer');
    
    if (!currentAssessment || !currentAssessment.questions || currentAssessment.questions.length === 0) {
        container.innerHTML = '<div class="error-message">No questions available.</div>';
        return;
    }

    container.innerHTML = currentAssessment.questions.map((question, index) => {
        const questionId = question.id;
        const options = question.options || [];
        const difficulty = question.difficulty || 'medium';

        return `
            <div class="question-card" id="question-${index}">
                <h3>
                    Question ${index + 1}
                    <span class="difficulty-badge difficulty-${difficulty}">${difficulty.toUpperCase()}</span>
                </h3>
                <div class="question-text">${question.question}</div>
                <div class="options">
                    ${options.map((option, optIndex) => {
                        const optionLabel = String.fromCharCode(65 + optIndex); // A, B, C, D
                        const optionId = `q${index}-opt${optIndex}`;
                        const isSelected = answers[questionId] === optionLabel;
                        
                        return `
                            <label class="option ${isSelected ? 'selected' : ''}" for="${optionId}">
                                <input 
                                    type="radio" 
                                    id="${optionId}"
                                    name="question-${questionId}" 
                                    value="${optionLabel}"
                                    ${isSelected ? 'checked' : ''}
                                    onchange="selectAnswer('${questionId}', '${optionLabel}')"
                                >
                                <strong>${optionLabel}.</strong> ${option}
                            </label>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }).join('');

    // Update current question indicator
    updateQuestionIndicator();
}

function selectAnswer(questionId, answer) {
    answers[questionId] = answer;
    
    // Update visual selection
    document.querySelectorAll(`input[name="question-${questionId}"]`).forEach(radio => {
        const label = radio.closest('.option');
        if (radio.checked) {
            label.classList.add('selected');
        } else {
            label.classList.remove('selected');
        }
    });

    updateQuestionIndicator();
}

function updateQuestionIndicator() {
    const answeredCount = Object.keys(answers).length;
    const totalQuestions = currentAssessment?.questions?.length || 0;
    
    // Find first unanswered question index
    let firstUnanswered = 0;
    for (let i = 0; i < totalQuestions; i++) {
        const questionId = currentAssessment.questions[i].id;
        if (!answers[questionId]) {
            firstUnanswered = i;
            break;
        }
    }
    
    currentQuestionIndex = firstUnanswered;
    document.getElementById('currentQuestion').textContent = currentQuestionIndex + 1;

    // Scroll to current question
    const currentQuestionElement = document.getElementById(`question-${currentQuestionIndex}`);
    if (currentQuestionElement) {
        currentQuestionElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Update submit button
    const submitBtn = document.getElementById('btnSubmit');
    if (answeredCount === totalQuestions) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Assessment';
    } else {
        submitBtn.disabled = false;
        submitBtn.textContent = `Submit Assessment (${answeredCount}/${totalQuestions} answered)`;
    }
}

function startTimer() {
    updateTimerDisplay();

    timerInterval = setInterval(() => {
        timeRemaining--;
        updateTimerDisplay();

        if (timeRemaining <= 0) {
            clearInterval(timerInterval);
            alert('Time is up! Submitting your assessment...');
            submitAssessment();
        }
    }, 1000);
}

function updateTimerDisplay() {
    const minutes = Math.floor(timeRemaining / 60);
    const seconds = timeRemaining % 60;
    document.getElementById('timeRemaining').textContent = 
        `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

async function submitAssessment() {
    // Check if attempt_id exists - try multiple sources
    if (!currentAttemptId) {
        // Try 1: Get from separate localStorage key
        currentAttemptId = localStorage.getItem('attempt_id');
        console.log('Attempt ID from localStorage:', currentAttemptId);
        
        // Try 2: Get from stored assessment data
        if (!currentAttemptId) {
            const storedAssessment = localStorage.getItem('currentAssessment');
            if (storedAssessment) {
                try {
                    const assessmentData = JSON.parse(storedAssessment);
                    currentAttemptId = assessmentData.attempt_id;
                    console.log('Attempt ID from assessment data:', currentAttemptId);
                    
                    // Store it separately for next time
                    if (currentAttemptId) {
                        localStorage.setItem('attempt_id', currentAttemptId);
                    }
                } catch (e) {
                    console.error('Error parsing stored assessment:', e);
                }
            }
        }
        
        // If still no attempt_id, show error
        if (!currentAttemptId) {
            console.error('❌ No attempt_id found in any source');
            console.error('   This usually means no user profile exists in the database.');
            console.error('   Please ensure at least one profile exists in the profiles table.');
            showError('No active assessment attempt. Please ensure at least one user profile exists in the database. Contact your administrator.');
            return;
        }
    }
    
    console.log('✅ Using attempt_id for submission:', currentAttemptId);

    // Disable submit button
    const submitBtn = document.getElementById('btnSubmit');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    if (timerInterval) {
        clearInterval(timerInterval);
    }

    try {
        // Prepare answers
        const answerList = Object.keys(answers).map(questionId => ({
            question_id: questionId,
            answer: answers[questionId] || ''
        }));

        // Submit to backend
        const response = await fetch(`${API_BASE_URL}/submitAssessment`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                attempt_id: currentAttemptId,
                answers: answerList
            })
        });

        const data = await response.json();

        if (data.success) {
            console.log('✅ Assessment submitted successfully:', data);
            
            // Clear localStorage (keep attempt_id for debugging if needed)
            localStorage.removeItem('currentAssessment');
            // Optionally clear attempt_id after successful submission
            // localStorage.removeItem('attempt_id');
            
            // Store results in localStorage for results page
            // Use both keys for compatibility
            localStorage.setItem('assessmentResults', JSON.stringify(data));
            localStorage.setItem('result_data', JSON.stringify(data)); // Also store as result_data for compatibility
            
            console.log('✅ Results stored in localStorage. Redirecting to results page...');
            
            // Add small delay to ensure localStorage is written
            setTimeout(() => {
                // Use window.location.assign for better reliability
                window.location.assign('/static/results.html');
            }, 100);
        } else {
            console.error('❌ Submission failed:', data);
            const errorMsg = data.error || data.detail || 'Failed to submit assessment';
            console.error('Error details:', errorMsg);
            showError(errorMsg);
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Assessment';
        }
    } catch (error) {
        console.error('Error submitting assessment:', error);
        showError('Error submitting assessment: ' + (error.message || String(error)));
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Assessment';
    }
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.style.display = 'block';
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    
    // Scroll to error
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

