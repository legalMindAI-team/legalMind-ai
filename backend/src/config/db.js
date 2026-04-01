const mongoose=require('mongoose');
const dotenv=require('dotenv');
dotenv.config();


const URL=process.env.MONGO_URI


const connectDb=async()=>{
    try{
        await mongoose.connect(URL)
        
        console.log('MongoDB connected successfully');
    }catch(error){
        console.error('MongoDB connection failed:', error.message);
        process.exit(1);
    }

}
module.exports=connectDb;