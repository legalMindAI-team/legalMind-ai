const multer = require('multer');
const path = require('path');


// Configure where & how files will be stored
const storage = multer.memoryStorage({
  //📁 Folder where files will be saved

  destination: (req, file, cb) => {
    cb(null, 'uploads/');
  },
  // Create unique filename to avoid duplicates
  filename: (req, file, cb) => {

    // Date.now() adds unique timestamp
    cb(null, `${Date.now()}-${file.originalname}`);
  },
});

//File filter to allow only images & PDFs
const fileFilter = (req, file, cb) => {

  //Allowed file extensions
  const allowedTypes = /jpeg|jpg|png|pdf/;

  //check extension 
  const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
  //check MIME type
  const mimetype = allowedTypes.test(file.mimetype);

  if (extname && mimetype) {
    cb(null, true);
  } else {
    cb(new Error('Only images and PDFs are allowed'));
  }
};

const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: 5 * 1024 * 1024 }, // 5MB
});

module.exports = upload;