// API Configuration - Auto-detect environment
// Use relative URL for production (Vercel), localhost for development
const API_BASE_URL = (() => {
    // If running on localhost, use localhost API
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://127.0.0.1:8000/api';
    }
    // For production (Vercel), use relative URL (same origin)
    return '/api';
})();

// State
let currentAttemptId = null;
let currentQuestions = [];
let answers = {};
let timerInterval = null;
let timeRemaining = 0;
let assessments = [];

// Initialize - Load courses directly
document.addEventListener('DOMContentLoaded', () => {
    loadCourses();
    loadProgress();
    loadRecentAssessments();
    
    // Auto-refresh data periodically (every 30 seconds) when on dashboard
    setInterval(() => {
        refreshChartData();
    }, 30000); // 30 seconds
    
    // Refresh data when page becomes visible (user returns from results page)
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            refreshChartData();
        }
    });
    
    // Also refresh on focus (when user switches back to tab)
    window.addEventListener('focus', () => {
        refreshChartData();
    });
});

// Refresh chart data from backend
async function refreshChartData() {
    try {
        const response = await fetch(`${API_BASE_URL}/getProgress`);
        const data = await response.json();
        
        if (data.success) {
            // Update stats
            document.getElementById('totalAssessmentsStat').textContent = data.total_assessments || 0;
            
            // Format average score with proper decimal handling
            const avgScore = data.avg_score !== undefined && data.avg_score !== null ? parseFloat(data.avg_score) : 0;
            const formattedAvg = avgScore.toFixed(1);
            document.getElementById('avgScoreStat').textContent = formattedAvg + '%';
            
            // Debug logging
            if (avgScore === 0 && (data.total_assessments || 0) > 0) {
                console.warn('Average score is 0 but assessments exist. Data:', {
                    total_assessments: data.total_assessments,
                    avg_score: data.avg_score,
                    recent_assessments: data.recent_assessments
                });
            }
            
            // Update topic mastery
            if (data.topic_mastery) {
                displayTopicMastery(data.topic_mastery);
            }
            
            // Update recent assessments list
            if (data.recent_assessments) {
                displayRecentAssessments(data.recent_assessments);
            }
        }
    } catch (error) {
        console.error('Error refreshing chart data:', error);
        // Silently fail - don't interrupt user experience
    }
}

// Get icon for skill
function getSkillIcon(skillName) {
    const icons = {
        'React': { class: 'react', symbol: '<>' },
        'JavaScript': { class: 'javascript', symbol: '<>' },
        'TypeScript': { class: 'typescript', symbol: '<>' },
        'Python': { class: 'python', symbol: '🐍' },
        'DevOps': { class: 'javascript', symbol: '∞' },
        'Problem Solving': { class: 'problem-solving', symbol: '🧠' },
        'Communication': { class: 'communication', symbol: '💬' },
        'Teamwork': { class: 'teamwork', symbol: '👥' },
        'Communication & Collaboration': { class: 'communication', symbol: '💬' }
    };
    
    // Try exact match first
    if (icons[skillName]) {
        return icons[skillName];
    }
    
    // Try partial match (case-insensitive)
    const skillLower = skillName.toLowerCase();
    for (const [key, value] of Object.entries(icons)) {
        if (skillLower.includes(key.toLowerCase())) {
            return value;
        }
    }
    
    // Check for common patterns
    if (skillLower.includes('python') || skillLower.includes('py_')) {
        return { class: 'python', symbol: '🐍' };
    }
    if (skillLower.includes('devops') || skillLower.includes('dev')) {
        return { class: 'javascript', symbol: '∞' };
    }
    
    // Default icon
    return { class: 'javascript', symbol: '<>' };
}

// Get difficulty display text
function getDifficultyText(difficulty) {
    const difficultyMap = {
        'easy': 'All Levels',
        'medium': 'Intermediate',
        'hard': 'Advanced',
        'all': 'All Levels'
    };
    return difficultyMap[difficulty.toLowerCase()] || difficulty;
}

// API Functions
async function loadCourses() {
    try {
        const response = await fetch(`${API_BASE_URL}/getAssessments`);
        const data = await response.json();

        if (data.success) {
            assessments = data.assessments;
            
            if (data.courses && data.courses.length > 0) {
                displayCoursesFromData(data.courses);
            } else {
                displayCourses(assessments);
            }
        } else {
            console.error('Failed to load assessments');
            document.getElementById('coursesList').innerHTML = '<p>No courses available</p>';
        }
    } catch (error) {
        console.error('Error loading courses:', error);
        document.getElementById('coursesList').innerHTML = '<p>Error loading courses. Please try again later.</p>';
    }
}

function displayCourses(assessmentsList) {
    const container = document.getElementById('coursesList');
    
    if (!assessmentsList || assessmentsList.length === 0) {
        container.innerHTML = '<p>No courses available</p>';
        return;
    }

    // Normalize domain name function (matches backend logic)
    function normalizeDomain(rawName) {
        if (!rawName || typeof rawName !== 'string') {
            return 'General';
        }
        
        // Convert to lowercase and trim
        let name = rawName.trim().toLowerCase();
        
        // Remove .pdf suffix
        if (name.endsWith('.pdf')) {
            name = name.slice(0, -4);
        }
        
        // Replace underscores with spaces
        name = name.replace(/_/g, ' ');
        
        // Trim again after replacements
        name = name.trim();
        
        if (!name) {
            return 'General';
        }
        
        // Capitalize each word (e.g., "python datatypes" -> "Python Datatypes")
        const words = name.split(/\s+/);
        const normalizedWords = words.map(word => {
            if (word.length === 0) return '';
            return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
        });
        
        return normalizedWords.join(' ');
    }

    // Group assessments by normalized skill_domain (case-insensitive, handles .pdf, underscores)
    const courses = {};
    
    assessmentsList.forEach(assessment => {
        // Get raw domain name (backend should normalize, but be defensive)
        const rawDomain = assessment.skill_name || assessment.skill_domain || 'General';
        
        // Normalize domain name (handles .pdf, underscores, case, whitespace)
        const normalizedName = normalizeDomain(rawDomain);
        
        // Use lowercase for grouping key (case-insensitive)
        const domainKey = normalizedName.toLowerCase();
        
        // Initialize course if it doesn't exist
        if (!courses[domainKey]) {
            courses[domainKey] = {
                name: normalizedName,  // Display name (normalized)
                displayName: normalizedName,  // For consistency
                originalName: rawDomain,  // Store original for reference
                assessments: [],
                totalTests: 0,
                uniqueSourceCount: 0,  // Will be set from backend if available
                uniqueTitles: new Set()  // Track unique assessment titles
            };
        }
        
        // Add assessment to the grouped course
        courses[domainKey].assessments.push(assessment);
        courses[domainKey].totalTests++;
        
        // Track unique titles (as proxy for unique sources)
        const title = assessment.title || assessment.skill_name || '';
        if (title) {
            const normalizedTitle = normalizeDomain(title).toLowerCase();
            courses[domainKey].uniqueTitles.add(normalizedTitle);
        }
    });

    // Display course cards
    container.innerHTML = Object.values(courses).map(course => {
        const icon = getSkillIcon(course.name);
        // Calculate progress based on unique source count
        // Use unique titles count as fallback if backend doesn't provide unique source count
        const uniqueCount = course.uniqueSourceCount || 
                           (course.uniqueTitles ? course.uniqueTitles.size : 0) || 
                           course.totalTests || 
                           1;
        const progress = Math.min(uniqueCount * 5, 100);
        const testLabel = uniqueCount === 1 ? 'Test' : 'Tests';
        
        return `
            <div class="course-card">
                <div class="course-header">
                    <div class="course-icon ${icon.class}">${icon.symbol}</div>
                    <h3>${course.name}</h3>
                </div>
                <div class="course-meta">
                    <p class="test-count">${uniqueCount} ${testLabel}</p>
                </div>
                <div class="progress-section">
                    <div class="progress-info">
                        <span>Progress</span>
                        <span>${progress}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                    </div>
                </div>
                <button class="view-assessments-btn" onclick="openCourse('${course.displayName.replace(/'/g, "\\'")}', '${course.id || ''}')">
                    View Assessments
                </button>
            </div>
        `;
    }).join('');
}

// New function to display courses from backend data (with unique source counts)
function displayCoursesFromData(coursesData) {
    const container = document.getElementById('coursesList');
    
    if (!coursesData || coursesData.length === 0) {
        container.innerHTML = '<p>No courses available</p>';
        return;
    }

    // Display course cards with unique source counts
    container.innerHTML = coursesData.map(course => {
        const icon = getSkillIcon(course.skill_domain || course.skill_name || course.name);
        const totalTests = course.test_count || 0;  // Use 0 if no tests, still show course
        const progress = course.progress || (totalTests > 0 ? Math.min(totalTests * 5, 100) : 0);
        const testLabel = totalTests === 1 ? 'Test' : 'Tests';
        
        return `
            <div class="course-card">
                <div class="course-header">
                    <div class="course-icon ${icon.class}">${icon.symbol}</div>
                    <h3>${course.skill_domain || course.skill_name}</h3>
                </div>
                <div class="course-meta">
                    <p class="test-count">${totalTests} ${testLabel}</p>
                </div>
                <div class="progress-section">
                    <div class="progress-info">
                        <span>Progress</span>
                        <span>${progress}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                    </div>
                </div>
                <button class="view-assessments-btn" onclick="openCourse('${(course.skill_domain || course.skill_name).replace(/'/g, "\\'")}', '${course.id || ''}')">
                    View Assessments
                </button>
            </div>
        `;
    }).join('');
}

function openCourse(courseName, courseId) {
    // Store selected course ID in localStorage (prefer courseId if available)
    if (courseId) {
        localStorage.setItem('selectedCourseId', courseId);
        localStorage.setItem('selectedCourse', courseName); // Keep for backward compatibility
        // Redirect to assessments page with course_id
        window.location.href = `/static/assessments.html?course_id=${courseId}`;
    } else {
        // Fallback to old method
        localStorage.setItem('selectedCourse', courseName);
        window.location.href = '/static/assessments.html';
    }
}

async function startAssessmentById(assessmentId, skillName, numQuestions) {
    // Get the button that was clicked
    const button = event?.target?.closest('.start-btn') || 
                   document.querySelector(`button[onclick*="${assessmentId}"]`);
    
    try {
        // Show loading state
        if (button) {
            button.disabled = true;
            button.innerHTML = '<span class="start-btn-icon">⏳</span> Loading...';
        }

        console.log(`Starting assessment: ${assessmentId}`);
        
        // Fetch questions from backend
        const response = await fetch(`${API_BASE_URL}/assessments/${assessmentId}/questions`);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
            throw new Error(errorData.detail || errorData.error || `Failed to fetch questions: HTTP ${response.status}`);
        }

        const data = await response.json();
        console.log('Assessment data received:', data);

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
            title: data.title || skillName,
            questions: data.questions,
            duration_minutes: data.duration_minutes || 30,
            started_at: data.started_at || new Date().toISOString()
        };
        
        localStorage.setItem('currentAssessment', JSON.stringify(assessmentData));
        
        // Also store attempt_id separately for reliability
        if (data.attempt_id) {
            localStorage.setItem('attempt_id', data.attempt_id);
            console.log('✅ Attempt ID stored separately:', data.attempt_id);
        } else {
            console.warn('⚠️  No attempt_id in response:', data);
        }
        
        console.log('✅ Assessment data stored in localStorage');
        
        // Redirect to assessment page
        console.log('Redirecting to assessment page...');
        window.location.href = '/static/assessment.html';
        
    } catch (error) {
        console.error('Error starting assessment:', error);
        
        // Re-enable button
        if (button) {
            button.disabled = false;
            button.innerHTML = '<span class="start-btn-icon">▶</span> Start Assessment';
        }
        
        // Show user-friendly error message
        alert(`Error starting assessment: ${error.message || 'Unknown error'}\n\nCheck the browser console for more details.`);
    }
}

function displayQuestions() {
    const container = document.getElementById('questionsContainer');
    const totalQuestions = currentQuestions.length;

    document.getElementById('totalQuestions').textContent = totalQuestions;

    container.innerHTML = currentQuestions.map((question, index) => {
        const questionId = question.id;
        const options = question.options || [];

        return `
            <div class="question-card" id="question-${index}">
                <h3>Question ${index + 1}</h3>
                <p style="margin-bottom: 15px; font-size: 16px;">${question.question}</p>
                <div class="options">
                    ${options.map((option, optIndex) => {
                        const optionLabel = String.fromCharCode(65 + optIndex);
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
}

function selectAnswer(questionId, answer) {
    answers[questionId] = answer;
    
    document.querySelectorAll(`input[name="question-${questionId}"]`).forEach(radio => {
        const label = radio.closest('.option');
        if (radio.checked) {
            label.classList.add('selected');
        } else {
            label.classList.remove('selected');
        }
    });
}

function startTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
    }

    updateTimerDisplay();

    timerInterval = setInterval(() => {
        timeRemaining--;
        updateTimerDisplay();

        if (timeRemaining <= 0) {
            clearInterval(timerInterval);
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
    if (!currentAttemptId) {
        console.error('No active assessment');
        return;
    }

    if (timerInterval) {
        clearInterval(timerInterval);
    }

    try {
        showLoading('Submitting assessment...');

        const answerList = Object.keys(answers).map(questionId => ({
            question_id: questionId,
            answer: answers[questionId] || ''
        }));

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
            displayResults(data);
            document.getElementById('questionsSection').style.display = 'none';
            document.getElementById('resultsSection').style.display = 'block';
            
            loadProgress();
            loadRecentAssessments();
        } else {
            showError(data.error || 'Failed to submit assessment');
        }
    } catch (error) {
        console.error('Error submitting assessment:', error);
        showError('Error submitting assessment: ' + error.message);
    }
}

function displayResults(data) {
    const container = document.getElementById('resultsContent');
    const percentage = data.percentage_score.toFixed(1);
    const passed = data.passed;

    container.innerHTML = `
        <div class="score">${percentage}%</div>
        <div class="score-info">
            Score: ${data.score} / ${data.max_score}
        </div>
        <div class="score-info">
            Correct: ${data.correct_count} / ${data.total_questions}
        </div>
        <div class="${passed ? 'success' : 'error'}" style="margin-top: 20px;">
            ${passed ? '✅ Passed!' : '❌ Not Passed'}
        </div>
    `;
}

function cancelAssessment() {
    if (confirm('Are you sure you want to cancel this assessment?')) {
        if (timerInterval) {
            clearInterval(timerInterval);
        }
        currentAttemptId = null;
        currentQuestions = [];
        answers = {};
        document.getElementById('questionsSection').style.display = 'none';
    }
}

function resetAssessment() {
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('questionsSection').style.display = 'none';
    currentAttemptId = null;
    currentQuestions = [];
    answers = {};
}

async function loadProgress() {
    try {
        const response = await fetch(`${API_BASE_URL}/getProgress`);
        const data = await response.json();

        if (data.success) {
            document.getElementById('totalAssessmentsStat').textContent = data.total_assessments || 0;
            
            // Format average score with proper decimal handling
            const avgScore = data.avg_score !== undefined && data.avg_score !== null ? parseFloat(data.avg_score) : 0;
            const formattedAvg = avgScore.toFixed(1);
            document.getElementById('avgScoreStat').textContent = formattedAvg + '%';
            
            // Debug logging
            if (avgScore === 0 && (data.total_assessments || 0) > 0) {
                console.warn('Average score is 0 but assessments exist. Data:', {
                    total_assessments: data.total_assessments,
                    avg_score: data.avg_score,
                    recent_assessments: data.recent_assessments
                });
            }
            
            // Update topic mastery
            if (data.topic_mastery) {
                displayTopicMastery(data.topic_mastery);
            }
        }
    } catch (error) {
        console.error('Error loading progress:', error);
    }
}

async function loadRecentAssessments() {
    try {
        const response = await fetch(`${API_BASE_URL}/getProgress`);
        const data = await response.json();

        if (data.success && data.recent_assessments) {
            displayRecentAssessments(data.recent_assessments);
        }
    } catch (error) {
        console.error('Error loading recent assessments:', error);
    }
}

function displayRecentAssessments(recentAssessments) {
    const container = document.getElementById('recentAssessmentsList');
    
    if (!recentAssessments || recentAssessments.length === 0) {
        container.innerHTML = '<p>No recent assessments</p>';
        return;
    }

    container.innerHTML = recentAssessments.map(assessment => {
        const score = Math.round(assessment.score);
        const maxScore = assessment.max_score || 100;
        const percentage = Math.round((score / maxScore) * 100);
        const date = new Date(assessment.date).toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric', 
            year: 'numeric' 
        });
        const attemptId = assessment.id; // This is the attempt_id from backend
        
        return `
            <div class="recent-assessment-card">
                <div class="recent-assessment-left">
                    <div class="recent-assessment-title">${assessment.skill_name}</div>
                    <div class="recent-assessment-meta">${date} • ${assessment.duration_minutes || 30} min</div>
                    <div class="recent-assessment-progress">
                        <div class="recent-assessment-progress-fill" style="width: ${percentage}%"></div>
                    </div>
                </div>
                <div class="recent-assessment-right">
                    <div class="score-badge">${score}/${maxScore}</div>
                    <div class="score-change">
                        <span>↑</span>
                        <span>+${Math.floor(Math.random() * 10) + 1}</span>
                    </div>
                    <button class="btn-review" onclick="reviewAssessment('${attemptId}', event)">Review</button>
                </div>
            </div>
        `;
    }).join('');
}

// Review assessment - navigate to results page
function reviewAssessment(attemptId, event) {
    if (!attemptId) {
        console.error('❌ No attempt_id provided for review');
        return;
    }
    
    console.log('🔍 Reviewing assessment attempt:', attemptId);
    
    // Prevent event propagation
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
    // Redirect to results page with attempt_id in URL
    window.location.href = `/static/results.html?attempt_id=${attemptId}`;
}

// Display Topic Mastery Scorecard
function displayTopicMastery(topicMastery) {
    const container = document.getElementById('topicMasteryList');
    
    if (!container) {
        console.warn('Topic mastery container not found');
        return;
    }
    
    if (!topicMastery || topicMastery.length === 0) {
        container.innerHTML = '<p class="no-topics-message">No topic data available. Complete assessments to see your mastery scores.</p>';
        return;
    }
    
    container.innerHTML = topicMastery.map(topic => {
        const percentage = Math.round(topic.percentage);
        const correct = topic.correct || 0;
        const total = topic.total || 0;
        
        // Determine color based on mastery level
        let progressColor = '#E5005B'; // Default pink
        if (percentage >= 80) {
            progressColor = '#28a745'; // Green for high mastery
        } else if (percentage >= 60) {
            progressColor = '#ffc107'; // Yellow for medium mastery
        } else if (percentage >= 40) {
            progressColor = '#fd7e14'; // Orange for low-medium mastery
        } else {
            progressColor = '#dc3545'; // Red for low mastery
        }
        
        return `
            <div class="topic-mastery-item">
                <div class="topic-mastery-header">
                    <span class="topic-name">${topic.topic}</span>
                    <span class="topic-percentage">${percentage}%</span>
                </div>
                <div class="topic-mastery-progress-bar">
                    <div class="topic-mastery-progress-fill" style="width: ${percentage}%; background-color: ${progressColor};"></div>
                </div>
                <div class="topic-mastery-stats">
                    <span class="topic-stats-text">${correct} / ${total} correct</span>
                </div>
            </div>
        `;
    }).join('');
}



// Utility Functions
function showLoading(message) {
    const container = document.getElementById('questionsContainer');
    if (container) {
        container.innerHTML = `<div class="loading">${message}</div>`;
    }
}

function showError(message) {
    // Convert objects to strings and log to console instead of showing alert
    let errorMessage = message;
    if (typeof message === 'object' && message !== null) {
        if (message.error) {
            errorMessage = message.error;
        } else if (message.detail) {
            errorMessage = message.detail;
        } else if (message.message) {
            errorMessage = message.message;
        } else {
            errorMessage = JSON.stringify(message);
        }
    }
    // Log error to console instead of showing alert
    console.error('Error:', errorMessage || 'An error occurred');
}

