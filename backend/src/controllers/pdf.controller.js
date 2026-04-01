const cloudinary = require('../config/cloudinary');
const File = require('../models/File.model'); 
const streamifier = require('streamifier');

exports.uploadAndForward = async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ message: "No file uploaded" });

    // 1. Upload Buffer to Cloudinary
    const streamUpload = (req) => {
      return new Promise((resolve, reject) => {
        const stream = cloudinary.uploader.upload_stream(
          { 
            folder: "", 
            resource_type: "raw" // Use "raw" for PDFs
          },
          (error, result) => {
            if (result) resolve(result);
            else reject(error);
          }
        );
        streamifier.createReadStream(req.file.buffer).pipe(stream);
      });
    };

    const cloudinaryResult = await streamUpload(req);

    // 2. Save Metadata to MongoDB
    const newFile = await File.create({
      fileName: req.file.originalname,
      cloudinaryUrl: cloudinaryResult.secure_url,
      public_id: cloudinaryResult.public_id,
      status: 'uploaded_successfully' // Changed status for testing
    });

    // 3. COMMENTED OUT PYTHON HAND-OFF FOR TESTING
    /*
    const pythonApiUrl = "http://localhost:8000/process-pdf"; 
    const pythonResponse = await axios.post(pythonApiUrl, {
      fileId: newFile._id,
      pdfUrl: newFile.cloudinaryUrl
    });
    */

    // 4. Return success response with the Cloudinary URL
    res.status(200).json({
      message: "Cloudinary upload successful!",
      cloudinary_url: newFile.cloudinaryUrl,
      mongo_data: newFile
    });

  } catch (error) {
    console.error("Cloudinary Test Error:", error);
    res.status(500).json({ 
        message: "Cloudinary upload failed", 
        error: error.message 
    });
  }
};