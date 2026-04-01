const express = require('express');
const upload = require('../middlewares/multer');
const { uploadAndForward } = require('../controllers/pdf.controller');
const router = express.Router();

const uploadPdf = upload.fields([
	{ name: 'file', maxCount: 1 },
	{ name: 'pdf', maxCount: 1 }
]);

const normalizeUploadedFile = (req, res, next) => {
	if (!req.file && req.files) {
		req.file = (req.files.file && req.files.file[0]) || (req.files.pdf && req.files.pdf[0]);
	}
	next();
};

router.post('/upload', uploadPdf, normalizeUploadedFile, uploadAndForward);

module.exports = router;