const mongoose = require('mongoose');

const chunkSchema = new mongoose.Schema({
    fileId: { 
        type: mongoose.Schema.Types.ObjectId, 
        ref: 'File', 
        required: true 
    },
    content: { type: String, required: true }, // The raw text snippet
    embedding: { 
        type: [Number], 
        required: true 
    }, // The vector array for AI search
    metadata: {
        pageNumber: Number,
        chunkIndex: Number
    }
});

// CRITICAL: You must create a Vector Search Index in MongoDB Atlas 
// on the 'embedding' field to make this work.
module.exports = mongoose.model('Chunk', chunkSchema);