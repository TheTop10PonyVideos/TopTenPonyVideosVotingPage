document.addEventListener('DOMContentLoaded', function() {
    const videoForm = document.getElementById('videoForm');
    const videoUrlInput = document.getElementById('videoUrl');
    const validateBtn = document.getElementById('validateBtn');
    const validationResults = document.getElementById('validationResults');
    const votedVideosList = document.getElementById('votedVideosList');
    const emptyVotes = document.getElementById('emptyVotes');
    const voteCountBadge = document.getElementById('voteCount');
    const submitVotesBtn = document.getElementById('submitVotesBtn');
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmModal'));
    const modalVoteList = document.getElementById('modalVoteList');
    const finalSubmitBtn = document.getElementById('finalSubmitBtn');
    const votedVideos = new Map();
    initializeVotedVideos();
    videoForm.addEventListener('submit', validateVideo);
    submitVotesBtn.addEventListener('click', showConfirmModal);
    finalSubmitBtn.addEventListener('click', submitVotes);
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    function initializeVotedVideos() {
        const videoItems = document.querySelectorAll('#votedVideosList li');
        videoItems.forEach(item => {
            const videoId = parseInt(item.dataset.videoId);
            const rankSelect = item.querySelector('.rank-select');
            votedVideos.set(videoId, {
                id: videoId,
                rank: parseInt(rankSelect.value)
            });
            rankSelect.addEventListener('change', updateRanking);
            item.querySelector('.remove-video').addEventListener('click', function() {
                removeVideo(videoId);
            });
        });
        updateVoteCount();
        updateSubmitButton();
    }
    function validateVideo(e) {
        e.preventDefault();
        const url = videoUrlInput.value.trim();
        if (!url) return;
        videoUrlInput.disabled = true;
        validateBtn.disabled = true;
        validateBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Validating...';
        validationResults.style.display = 'none';
        const headers = {
            'Content-Type': 'application/json'
        };
        const csrfTokenElement = document.querySelector('input[name="csrf_token"]');
        if (csrfTokenElement) {
            headers['X-CSRFToken'] = csrfTokenElement.value;
        }
        fetch('/validate-video', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ url: url })
        })
        .then(response => response.json())
        .then(data => {
            videoUrlInput.disabled = false;
            validateBtn.disabled = false;
            validateBtn.innerHTML = '<i class="fas fa-search me-1"></i> Validate';
            if (data.valid) {
                if (data.similar) {
                    showSimilarVideoAlert(data);
                } else {
                    addVideoToList(data.video);
                    videoUrlInput.value = '';
                }
            } else {
                showValidationError(data.message);
            }
        })
        .catch(error => {
            console.error('Error validating video:', error);
            videoUrlInput.disabled = false;
            validateBtn.disabled = false;
            validateBtn.innerHTML = '<i class="fas fa-search me-1"></i> Validate';
            showValidationError('An error occurred while validating the video. Please try again.');
        });
    }
    function showValidationError(message) {
        validationResults.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle me-2"></i> ${message}
            </div>
        `;
        validationResults.style.display = 'block';
    }
    function showSimilarVideoAlert(data) {
        const video = data.original_video;
        validationResults.innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i> ${data.message}
                <hr>
                <div class="d-flex align-items-center">
                    ${video.thumbnail_url ? 
                        `<img src="${video.thumbnail_url}" class="me-2" alt="${video.title}" style="width: 60px; height: 45px; object-fit: cover;">` : 
                        `<div class="me-2 bg-secondary d-flex align-items-center justify-content-center" style="width: 60px; height: 45px;">
                            <i class="fas fa-film"></i>
                        </div>`
                    }
                    <div>
                        <strong>${video.title}</strong><br>
                        <small>${video.creator_name} (${video.platform})</small>
                    </div>
                </div>
                <div class="d-flex justify-content-between mt-2">
                    <button class="btn btn-sm btn-secondary" onclick="window.open('${data.original_video.url}', '_blank')">
                        View Original
                    </button>
                    <button class="btn btn-sm btn-primary" id="useExistingVideoBtn">
                        Use This Video Instead
                    </button>
                </div>
            </div>
        `;
        validationResults.style.display = 'block';
        document.getElementById('useExistingVideoBtn').addEventListener('click', function() {
            addVideoToList(data.original_video);
            validationResults.style.display = 'none';
            videoUrlInput.value = '';
        });
    }
    function addVideoToList(video) {
        if (votedVideos.has(video.id)) {
            showValidationError(`This video is already in your voting list.`);
            return;
        }
        if (votedVideos.size >= 10) {
            showValidationError(`You can only vote for a maximum of 10 videos.`);
            return;
        }
        const nextRank = getNextAvailableRank();
        votedVideos.set(video.id, {
            id: video.id,
            rank: nextRank
        });
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.dataset.videoId = video.id;
        const rankSelect = document.createElement('select');
        rankSelect.className = 'form-select me-2 rank-select';
        for (let i = 1; i <= 10; i++) {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = i;
            if (i === nextRank) option.selected = true;
            rankSelect.appendChild(option);
        }
        rankSelect.addEventListener('change', updateRanking);
        const thumbnailHtml = video.thumbnail_url ? 
            `<img src="${video.thumbnail_url}" class="me-2" alt="${video.title}" style="width: 60px; height: 45px; object-fit: cover;">` : 
            `<div class="me-2 bg-secondary d-flex align-items-center justify-content-center" style="width: 60px; height: 45px;">
                <i class="fas fa-film"></i>
            </div>`;
        li.innerHTML = `
            <div class="d-flex align-items-center">
                ${rankSelect.outerHTML}
                <div class="d-flex align-items-center">
                    ${thumbnailHtml}
                    <div>
                        <div class="text-truncate" style="max-width: 180px;" title="${video.title}">${video.title}</div>
                        <small class="text-muted">${video.creator_name}</small>
                    </div>
                </div>
            </div>
            <button class="btn btn-sm btn-danger remove-video">
                <i class="fas fa-times"></i>
            </button>
        `;
        li.querySelector('.remove-video').addEventListener('click', function() {
            removeVideo(video.id);
        });
        li.querySelector('.rank-select').addEventListener('change', updateRanking);
        votedVideosList.appendChild(li);
        if (emptyVotes) emptyVotes.classList.add('d-none');
        updateVoteCount();
        updateSubmitButton();
    }
    function removeVideo(videoId) {
        votedVideos.delete(videoId);
        const li = document.querySelector(`#votedVideosList li[data-video-id="${videoId}"]`);
        if (li) li.remove();
        if (votedVideos.size === 0 && emptyVotes) {
            emptyVotes.classList.remove('d-none');
        }
        updateVoteCount();
        updateSubmitButton();
    }
    function getNextAvailableRank() {
        const usedRanks = Array.from(votedVideos.values()).map(v => v.rank);
        for (let i = 1; i <= 10; i++) {
            if (!usedRanks.includes(i)) {
                return i;
            }
        }
        return 10;
    }
    function updateRanking(e) {
        const select = e.target;
        const li = select.closest('li');
        const videoId = parseInt(li.dataset.videoId);
        const newRank = parseInt(select.value);
        votedVideos.forEach((video, id) => {
            if (id !== videoId && video.rank === newRank) {
                const oldRank = votedVideos.get(videoId).rank;
                video.rank = oldRank;
                const otherLi = document.querySelector(`#votedVideosList li[data-video-id="${id}"]`);
                if (otherLi) {
                    const otherSelect = otherLi.querySelector('.rank-select');
                    otherSelect.value = oldRank;
                }
            }
        });
        if (votedVideos.has(videoId)) {
            votedVideos.get(videoId).rank = newRank;
        }
    }
    function updateVoteCount() {
        if (voteCountBadge) {
            voteCountBadge.textContent = `${votedVideos.size}/10`;
        }
    }
    function updateSubmitButton() {
        if (submitVotesBtn) {
            submitVotesBtn.disabled = votedVideos.size < 5 || votedVideos.size > 10;
        }
    }
    function showConfirmModal() {
        if (votedVideos.size < 5 || votedVideos.size > 10) {
            return;
        }
        if (votedVideos.size <= 5) {
            const creatorNames = new Set();
            let duplicateFound = false;
            document.querySelectorAll('#votedVideosList li').forEach(li => {
                const creatorName = li.querySelector('small.text-muted').textContent;
                if (creatorNames.has(creatorName)) {
                    duplicateFound = true;
                }
                creatorNames.add(creatorName);
            });
            if (duplicateFound) {
                showValidationError('When voting for 5 or fewer videos, all videos must be from different creators.');
                return;
            }
        }
        if (modalVoteList) {
            const sortedVideos = Array.from(document.querySelectorAll('#votedVideosList li'))
                .map(li => {
                    const videoId = parseInt(li.dataset.videoId);
                    const rank = parseInt(li.querySelector('.rank-select').value);
                    const title = li.querySelector('.text-truncate').textContent;
                    const creator = li.querySelector('small.text-muted').textContent;
                    return { id: videoId, rank, title, creator };
                })
                .sort((a, b) => a.rank - b.rank);
            modalVoteList.innerHTML = `
                <ul class="list-group mt-3">
                    ${sortedVideos.map(video => `
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span class="badge bg-primary me-2">#${video.rank}</span>
                            <div class="ms-2 me-auto">
                                <div class="fw-bold">${video.title}</div>
                                ${video.creator}
                            </div>
                        </li>
                    `).join('')}
                </ul>
            `;
        }
        confirmModal.show();
    }
    function submitVotes() {
        const votes = Array.from(votedVideos.entries()).map(([id, data]) => ({
            video_id: id,
            rank: data.rank
        }));
        const submitHeaders = {
            'Content-Type': 'application/json'
        };
        const submitCsrfTokenElement = document.querySelector('input[name="csrf_token"]');
        if (submitCsrfTokenElement) {
            submitHeaders['X-CSRFToken'] = submitCsrfTokenElement.value;
        }
        finalSubmitBtn.disabled = true;
        finalSubmitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Submitting...';
        fetch('/vote', {
            method: 'POST',
            headers: submitHeaders,
            body: JSON.stringify({ votes: votes })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                confirmModal.hide();
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-success alert-dismissible fade show';
                alertDiv.innerHTML = `
                    <i class="fas fa-check-circle me-2"></i> ${data.message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;
                const container = document.querySelector('.container');
                container.insertBefore(alertDiv, container.firstChild);
                window.scrollTo(0, 0);
                setTimeout(() => {
                    finalSubmitBtn.disabled = false;
                    finalSubmitBtn.innerHTML = 'Submit Votes';
                }, 1000);
            } else {
                confirmModal.hide();
                showValidationError(data.message || 'An error occurred while submitting votes.');
                finalSubmitBtn.disabled = false;
                finalSubmitBtn.innerHTML = 'Submit Votes';
            }
        })
        .catch(error => {
            console.error('Error submitting votes:', error);
            confirmModal.hide();
            showValidationError('An error occurred while submitting your votes. Please try again.');
            finalSubmitBtn.disabled = false;
            finalSubmitBtn.innerHTML = 'Submit Votes';
        });
    }
});
