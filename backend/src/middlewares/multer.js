const multer = require('multer');

// Use memory storage to handle the file as a buffer
const storage = multer.memoryStorage();

const fileFilter = (req, file, cb) => {
  // Allow only PDFs for your RAG model
  if (file.mimetype === 'application/pdf') {
    cb(null, true);
  } else {
    cb(new Error('Only PDF files are allowed!'), false);
  }
};

const upload = multer({
  storage: storage,
  fileFilter: fileFilter,
  limits: { fileSize: 10 * 1024 * 1024 } // 10MB limit
});

module.exports = upload;