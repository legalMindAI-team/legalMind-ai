// models/File.js
const mongoose = require('mongoose');

const fileSchema = new mongoose.Schema({
    fileName: String,
    cloudinaryUrl: String,
    public_id: String,
    pythonStatus: { type: String, default: 'pending' }, // track if Python finished
    createdAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model('File', fileSchema);