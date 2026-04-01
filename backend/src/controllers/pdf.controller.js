const cloudinary = require('../config/cloudinary');
const File = require('../models/File.model'); 
const streamifier = require('streamifier');
const axios = require('axios');

exports.uploadAndForward = async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ message: "No file uploaded" });

    // 1. Upload Buffer to Cloudinary
    const streamUpload = (req) => {
      return new Promise((resolve, reject) => {
        const stream = cloudinary.uploader.upload_stream(
          { 
            folder: "legalmind_pdfs", 
            resource_type: "raw",
            access_mode: "public"
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
    const pdfUrl = cloudinaryResult.secure_url;

    // 2. Save Metadata to MongoDB
    const newFile = await File.create({
      fileName: req.file.originalname,
      cloudinaryUrl: pdfUrl,
      public_id: cloudinaryResult.public_id,
      status: 'uploaded_successfully' // Changed status for testing
    });

    // 3. Hand-off to Python AI Server (FastAPI)
    try {
      const pythonApiUrl = process.env.AI_SERVER_URL || 'http://127.0.0.1:8000/ai/ingest';
      
      console.log(`[Backend] Calling AI Engine at: ${pythonApiUrl}`);
      const pythonResponse = await axios.post(
        pythonApiUrl,
        {
          document_id: newFile._id.toString(),
          file_url: newFile.cloudinaryUrl
        },
        { timeout: 30000 }
      );
      
      console.log("[Backend] AI Engine Response:", pythonResponse.data);
    } catch (aiError) {
      console.error("[Backend] Failed to trigger AI Engine:", aiError.message);
      if (aiError.response && aiError.response.data) {
        console.error("[Backend] AI Engine Error Details:", aiError.response.data);
      }
      // Note: We're not throwing an error here, so sending the response to Harim continues
      // but you could mark status as 'failed_ingestion' later
    }

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