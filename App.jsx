import { motion } from "framer-motion";
import { 
  Sparkles, 
  Layout, 
  Code, 
  Palette, 
  ArrowRight, 
  Github,
  Twitter,
  Linkedin
} from "lucide-react";

export default function App() {
  const features = [
    {
      icon: Layout,
      title: "Modern Design",
      description: "Beautiful, intuitive interfaces crafted with the latest design principles"
    },
    {
      icon: Code,
      title: "Clean Code",
      description: "Well-structured, maintainable code following industry best practices"
    },
    {
      icon: Palette,
      title: "Custom Branding",
      description: "Unique color schemes and typography tailored to your brand identity"
    }
  ];

  const testimonials = [
    {
      quote: "This website transformed our online presence and increased conversions by 200%.",
      author: "Sarah Johnson",
      role: "CEO at TechStart"
    },
    {
      quote: "The attention to detail and responsiveness exceeded our expectations.",
      author: "Michael Chen",
      role: "Marketing Director"
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50 text-slate-800">
      {/* Navigation */}
      <nav className="container mx-auto px-4 py-6 flex justify-between items-center">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-8 h-8 text-indigo-600" />
          <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-purple-600">
            DesignCraft
          </span>
        </div>
        <div className="hidden md:flex space-x-8">
          <a href="#features" className="hover:text-indigo-600 transition-colors font-medium">Features</a>
          <a href="#testimonials" className="hover:text-indigo-600 transition-colors font-medium">Testimonials</a>
          <a href="#contact" className="hover:text-indigo-600 transition-colors font-medium">Contact</a>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-full font-medium transition-all transform hover:scale-105 shadow-lg">
          Get Started
        </button>
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-16 md:py-24 flex flex-col md:flex-row items-center">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="md:w-1/2 mb-12 md:mb-0"
        >
          <h1 className="text-4xl md:text-5xl font-extrabold mb-6 leading-tight">
            Beautiful Websites <span className="text-indigo-600">Crafted</span> with Precision
          </h1>
          <p className="text-xl text-slate-600 mb-8 max-w-lg">
            Transform your digital presence with stunning, responsive websites designed to engage users and drive results.
          </p>
          <div className="flex flex-col sm:flex-row gap-4">
            <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-3 rounded-full font-medium text-lg transition-all transform hover:scale-105 flex items-center justify-center">
              Start Project <ArrowRight className="ml-2 w-5 h-5" />
            </button>
            <button className="border-2 border-slate-300 hover:border-indigo-600 text-slate-700 hover:text-indigo-600 px-8 py-3 rounded-full font-medium transition-all">
              View Portfolio
            </button>
          </div>
        </motion.div>
        <motion.div 
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="md:w-1/2"
        >
          <div className="bg-slate-200 border-2 border-dashed rounded-xl w-full h-64 md:h-80" />
        </motion.div>
      </section>

      {/* Features */}
      <section id="features" className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Why Choose Our Designs</h2>
            <p className="text-xl text-slate-600 max-w-3xl mx-auto">
              We combine aesthetics with functionality to create websites that not only look great but also deliver exceptional user experiences.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="bg-slate-50 p-8 rounded-2xl hover:shadow-xl transition-shadow"
              >
                <feature.icon className="w-12 h-12 text-indigo-600 mb-6" />
                <h3 className="text-2xl font-bold mb-4">{feature.title}</h3>
                <p className="text-slate-600">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section id="testimonials" className="py-16 bg-gradient-to-br from-indigo-50 to-purple-50">
        <div className="container mx-auto px-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl md:text-4xl font-bold mb-4">What Our Clients Say</h2>
            <p className="text-xl text-slate-600 max-w-3xl mx-auto">
              Don't just take our word for it - hear from businesses that have transformed their online presence with our designs.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {testimonials.map((testimonial, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="bg-white p-8 rounded-2xl shadow-md"
              >
                <p className="text-xl italic text-slate-700 mb-6">"{testimonial.quote}"</p>
                <div className="flex items-center">
                  <div className="bg-slate-200 border-2 border-dashed rounded-xl w-12 h-12 mr-4" />
                  <div>
                    <h4 className="font-bold text-lg">{testimonial.author}</h4>
                    <p className="text-slate-600">{testimonial.role}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 bg-indigo-600 text-white">
        <div className="container mx-auto px-4 text-center">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-3xl md:text-4xl font-bold mb-6"
          >
            Ready to Elevate Your Online Presence?
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-xl mb-8 max-w-3xl mx-auto"
          >
            Let's work together to create a website that not only looks stunning but also drives real business results.
          </motion.p>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="bg-white text-indigo-600 hover:bg-slate-100 px-8 py-3 rounded-full text-lg font-medium transition-colors"
          >
            Schedule a Free Consultation
          </motion.button>
        </div>
      </section>

      {/* Footer */}
      <footer id="contact" className="py-12 bg-slate-800 text-slate-300">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <Sparkles className="w-6 h-6 text-indigo-400" />
                <span className="text-xl font-bold text-white">DesignCraft</span>
              </div>
              <p className="mb-4">
                Creating beautiful digital experiences that help businesses grow and thrive.
              </p>
              <div className="flex space-x-4">
                <a href="#" className="text-slate-400 hover:text-white transition-colors">
                  <Github className="w-5 h-5" />
                </a>
                <a href="#" className="text-slate-400 hover:text-white transition-colors">
                  <Twitter className="w-5 h-5" />
                </a>
                <a href="#" className="text-slate-400 hover:text-white transition-colors">
                  <Linkedin className="w-5 h-5" />
                </a>
              </div>
            </div>
            
            <div>
              <h3 className="text-white font-semibold mb-4">Services</h3>
              <ul className="space-y-2">
                <li><a href="#" className="hover:text-white transition-colors">Web Design</a></li>
                <li><a href="#" className="hover:text-white transition-colors">UI/UX Design</a></li>
                <li><a href="#" className="hover:text-white transition-colors">E-Commerce</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Brand Identity</a></li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-white font-semibold mb-4">Company</h3>
              <ul className="space-y-2">
                <li><a href="#" className="hover:text-white transition-colors">About Us</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Portfolio</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Careers</a></li>
              </ul>
            </div>
            
            <div>
              <h3 className="text-white font-semibold mb-4">Contact</h3>
              <ul className="space-y-2">
                <li>hello@designcraft.com</li>
                <li>+1 (555) 123-4567</li>
                <li>123 Design Street, Creative City, CA 94107</li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-slate-700 mt-12 pt-8 text-center text-slate-400">
            <p>&copy; {new Date().getFullYear()} DesignCraft. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
