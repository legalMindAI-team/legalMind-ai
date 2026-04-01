const dns = require('dns');
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const dotenv = require('dotenv');
const multer = require('multer');
const connectDb = require('./src/config/db');
const pdfRoutes = require('./src/routes/pdfRoutes');
// const { Pool } = require('pg');

const app = express();

// Middleware
app.use(cors());
app.use(bodyParser.json());
dotenv.config();

const port = process.env.PORT || 3000;
// Set custom DNS servers to resolve MongoDB SRV records
dns.setServers(['1.1.1.1', '8.8.8.8']);

// Routes
app.get('/api/data', (req, res) => {
    res.json({ message: 'Hello from the backend!' });
});

app.use('/api/pdfs', pdfRoutes);

// Handle Multer upload errors with user-friendly responses
app.use((err, req, res, next) => {
    if (err instanceof multer.MulterError) {
        return res.status(400).json({
            message: 'File upload failed',
            error: err.message
        });
    }

    if (err && err.message === 'Only PDF files are allowed!') {
        return res.status(400).json({
            message: 'File upload failed',
            error: err.message
        });
    }

    return next(err);
});

// Start the server
connectDb().then(() => {
    console.log('Connected to MongoDB');
    app.listen(port, () => {
        console.log(`Server is running on http://localhost:${port}`);
    });
});
