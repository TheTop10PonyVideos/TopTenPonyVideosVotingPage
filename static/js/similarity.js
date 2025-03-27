function calculateStringSimilarity(str1, str2) {
    if (!str1 || !str2) return 0;
    str1 = normalizeString(str1);
    str2 = normalizeString(str2);
    if (str1 === str2) return 1.0;
    const distance = levenshteinDistance(str1, str2);
    const maxLength = Math.max(str1.length, str2.length);
    return 1 - (distance / maxLength);
}
function normalizeString(str) {
    str = str.toLowerCase();
    const commonWords = ['the', 'a', 'an', 'and', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'official', 'hd', 'video'];
    let words = str.split(/\s+/);
    words = words.filter(word => !commonWords.includes(word));
    return words.join(' ').replace(/[^\w\s]/g, '').trim();
}
function levenshteinDistance(str1, str2) {
    const matrix = Array(str1.length + 1).fill().map(() => Array(str2.length + 1).fill(0));
    for (let i = 0; i <= str1.length; i++) {
        matrix[i][0] = i;
    }
    for (let j = 0; j <= str2.length; j++) {
        matrix[0][j] = j;
    }
    for (let i = 1; i <= str1.length; i++) {
        for (let j = 1; j <= str2.length; j++) {
            const cost = str1.charAt(i - 1) === str2.charAt(j - 1) ? 0 : 1;
            matrix[i][j] = Math.min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + cost
            );
        }
    }
    return matrix[str1.length][str2.length];
}
function areVideosSimilar(video1, video2, threshold = 0.8) {
    if (!video1 || !video2) return false;
    const titleSimilarity = calculateStringSimilarity(video1.title, video2.title);
    const creatorSimilarity = calculateStringSimilarity(video1.creator, video2.creator);
    const weightedSimilarity = (titleSimilarity * 0.7) + (creatorSimilarity * 0.3);
    return weightedSimilarity >= threshold;
}
function generateVideoFingerprint(video) {
    if (!video || !video.title) return '';
    const normalizedTitle = normalizeString(video.title);
    const normalizedCreator = video.creator ? normalizeString(video.creator) : '';
    return hashString(`${normalizedTitle}|${normalizedCreator}`);
}
function hashString(str) {
    let hash = 0;
    if (str.length === 0) return hash.toString(16);
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return Math.abs(hash).toString(16);
}