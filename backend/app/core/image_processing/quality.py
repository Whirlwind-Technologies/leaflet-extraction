"""
Image Quality Scorer Module.

Analyzes and scores extracted product images for quality metrics
including clarity, completeness, and content detection.

Example Usage:
    from app.core.image_processing.quality import QualityScorer
    
    scorer = QualityScorer()
    report = scorer.analyze(image)
    print(f"Quality score: {report.overall_score}")
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageStat, ImageFilter
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """
    Quality analysis report for an image.
    
    Attributes:
        overall_score: Overall quality score (0.0-1.0)
        sharpness_score: Image sharpness (0.0-1.0)
        brightness_score: Brightness quality (0.0-1.0)
        contrast_score: Contrast quality (0.0-1.0)
        completeness_score: Content completeness (0.0-1.0)
        issues: List of identified issues
        recommendations: List of improvement suggestions
        metrics: Raw metric values
        is_acceptable: Whether image passes quality threshold
    """
    overall_score: float = 0.0
    sharpness_score: float = 0.0
    brightness_score: float = 0.0
    contrast_score: float = 0.0
    completeness_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)
    is_acceptable: bool = False


class QualityScorer:
    """
    Analyzes image quality for product images.
    
    Evaluates multiple quality dimensions including sharpness,
    brightness, contrast, and content completeness. Provides
    actionable feedback for quality improvements.
    
    Attributes:
        min_acceptable_score: Minimum overall score for acceptance
        sharpness_weight: Weight for sharpness in overall score
        brightness_weight: Weight for brightness in overall score
        contrast_weight: Weight for contrast in overall score
        completeness_weight: Weight for completeness in overall score
        
    Example:
        >>> scorer = QualityScorer(min_acceptable_score=0.7)
        >>> report = scorer.analyze(product_image)
        >>> if report.is_acceptable:
        ...     print("Image quality is acceptable")
        >>> else:
        ...     print(f"Issues: {report.issues}")
    """
    
    # Default weights for score calculation
    WEIGHTS = {
        "sharpness": 0.30,
        "brightness": 0.20,
        "contrast": 0.20,
        "completeness": 0.30,
    }
    
    # Thresholds for quality metrics
    THRESHOLDS = {
        "min_sharpness": 50,      # Laplacian variance threshold
        "max_sharpness": 2000,    # Too sharp might be artifact
        "min_brightness": 30,     # Mean brightness threshold
        "max_brightness": 225,    # Overexposure threshold
        "min_contrast": 20,       # Standard deviation threshold
        "min_edge_ratio": 0.05,   # Edge pixels ratio
        "min_content_ratio": 0.3, # Non-white content ratio
    }
    
    def __init__(
        self,
        min_acceptable_score: float = 0.70,
        weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the quality scorer.
        
        Args:
            min_acceptable_score: Minimum score for acceptance
            weights: Custom weights for quality dimensions
        """
        self.min_acceptable_score = min_acceptable_score
        self.weights = weights or self.WEIGHTS.copy()
    
    def analyze(self, image: Image.Image) -> QualityReport:
        """
        Perform comprehensive quality analysis on an image.
        
        Args:
            image: PIL Image to analyze
            
        Returns:
            QualityReport with scores and recommendations
        """
        report = QualityReport()
        issues = []
        recommendations = []
        
        try:
            # Convert to grayscale for analysis
            if image.mode != "L":
                gray = image.convert("L")
            else:
                gray = image
            
            # Analyze each quality dimension
            report.sharpness_score, sharpness_issues = self._analyze_sharpness(gray)
            issues.extend(sharpness_issues)
            
            report.brightness_score, brightness_issues = self._analyze_brightness(gray)
            issues.extend(brightness_issues)
            
            report.contrast_score, contrast_issues = self._analyze_contrast(gray)
            issues.extend(contrast_issues)
            
            report.completeness_score, completeness_issues = self._analyze_completeness(image)
            issues.extend(completeness_issues)
            
            # Calculate overall score
            report.overall_score = (
                report.sharpness_score * self.weights["sharpness"] +
                report.brightness_score * self.weights["brightness"] +
                report.contrast_score * self.weights["contrast"] +
                report.completeness_score * self.weights["completeness"]
            )
            
            # Store raw metrics
            report.metrics = self._collect_metrics(image, gray)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(report)
            
            # Determine acceptability
            report.is_acceptable = report.overall_score >= self.min_acceptable_score
            
            report.issues = issues
            report.recommendations = recommendations
            
            logger.debug(
                f"Quality analysis complete: score={report.overall_score:.2f}, "
                f"acceptable={report.is_acceptable}"
            )
            
        except Exception as e:
            logger.error(f"Quality analysis failed: {e}")
            report.issues = [f"Analysis failed: {str(e)}"]
            report.is_acceptable = False
        
        return report
    
    def _analyze_sharpness(
        self,
        gray: Image.Image,
    ) -> Tuple[float, List[str]]:
        """
        Analyze image sharpness using Laplacian variance.
        
        Args:
            gray: Grayscale PIL Image
            
        Returns:
            Tuple of (score, issues)
        """
        issues = []
        
        try:
            # Convert to numpy array
            img_array = np.array(gray, dtype=np.float64)
            
            # Calculate Laplacian variance (sharpness measure)
            # Using simple convolution approximation
            laplacian = np.array([
                [0, 1, 0],
                [1, -4, 1],
                [0, 1, 0]
            ])
            
            # Apply convolution (simplified)
            from scipy.ndimage import convolve
            lap_image = convolve(img_array, laplacian)
            variance = lap_image.var()
            
            # Normalize to 0-1 score
            if variance < self.THRESHOLDS["min_sharpness"]:
                score = variance / self.THRESHOLDS["min_sharpness"]
                issues.append("Image appears blurry")
            elif variance > self.THRESHOLDS["max_sharpness"]:
                score = 0.8  # Still acceptable but might have artifacts
                issues.append("Image may have oversharpening artifacts")
            else:
                # Good sharpness range
                score = min(1.0, 0.7 + (variance - self.THRESHOLDS["min_sharpness"]) / 
                           (self.THRESHOLDS["max_sharpness"] - self.THRESHOLDS["min_sharpness"]) * 0.3)
            
            return max(0, min(1, score)), issues
            
        except ImportError:
            # Fallback without scipy
            return self._analyze_sharpness_simple(gray)
        except Exception as e:
            logger.warning(f"Sharpness analysis failed: {e}")
            return 0.5, ["Could not analyze sharpness"]
    
    def _analyze_sharpness_simple(
        self,
        gray: Image.Image,
    ) -> Tuple[float, List[str]]:
        """Simple sharpness analysis without scipy."""
        issues = []
        
        try:
            # Use PIL's edge detection
            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            
            edge_mean = edge_stat.mean[0]
            
            # Normalize
            if edge_mean < 10:
                score = edge_mean / 10 * 0.5
                issues.append("Image appears blurry")
            elif edge_mean > 100:
                score = 0.9
            else:
                score = 0.5 + (edge_mean - 10) / 90 * 0.4
            
            return max(0, min(1, score)), issues
            
        except Exception as e:
            logger.warning(f"Simple sharpness analysis failed: {e}")
            return 0.5, []
    
    def _analyze_brightness(
        self,
        gray: Image.Image,
    ) -> Tuple[float, List[str]]:
        """
        Analyze image brightness.
        
        Args:
            gray: Grayscale PIL Image
            
        Returns:
            Tuple of (score, issues)
        """
        issues = []
        
        try:
            stat = ImageStat.Stat(gray)
            mean_brightness = stat.mean[0]
            
            if mean_brightness < self.THRESHOLDS["min_brightness"]:
                score = mean_brightness / self.THRESHOLDS["min_brightness"] * 0.5
                issues.append("Image is too dark")
            elif mean_brightness > self.THRESHOLDS["max_brightness"]:
                score = 0.5 * (255 - mean_brightness) / (255 - self.THRESHOLDS["max_brightness"])
                issues.append("Image is overexposed")
            else:
                # Optimal brightness is around 128
                optimal = 128
                distance = abs(mean_brightness - optimal)
                max_distance = max(optimal - self.THRESHOLDS["min_brightness"],
                                   self.THRESHOLDS["max_brightness"] - optimal)
                score = 1.0 - (distance / max_distance) * 0.3
            
            return max(0, min(1, score)), issues
            
        except Exception as e:
            logger.warning(f"Brightness analysis failed: {e}")
            return 0.5, []
    
    def _analyze_contrast(
        self,
        gray: Image.Image,
    ) -> Tuple[float, List[str]]:
        """
        Analyze image contrast.
        
        Args:
            gray: Grayscale PIL Image
            
        Returns:
            Tuple of (score, issues)
        """
        issues = []
        
        try:
            stat = ImageStat.Stat(gray)
            std_dev = stat.stddev[0]
            
            if std_dev < self.THRESHOLDS["min_contrast"]:
                score = std_dev / self.THRESHOLDS["min_contrast"] * 0.5
                issues.append("Image has low contrast")
            else:
                # Good contrast range 20-80
                optimal_max = 80
                if std_dev > optimal_max:
                    score = 0.9  # High contrast is usually fine
                else:
                    score = 0.5 + (std_dev - self.THRESHOLDS["min_contrast"]) / \
                           (optimal_max - self.THRESHOLDS["min_contrast"]) * 0.5
            
            return max(0, min(1, score)), issues
            
        except Exception as e:
            logger.warning(f"Contrast analysis failed: {e}")
            return 0.5, []
    
    def _analyze_completeness(
        self,
        image: Image.Image,
    ) -> Tuple[float, List[str]]:
        """
        Analyze content completeness.
        
        Checks for:
        - Edge content (potential cutoff)
        - Content ratio (not too much whitespace)
        - Aspect ratio reasonability
        
        Args:
            image: PIL Image
            
        Returns:
            Tuple of (score, issues)
        """
        issues = []
        score = 1.0
        
        try:
            width, height = image.size
            
            # Check aspect ratio
            aspect_ratio = width / height if height > 0 else 0
            if aspect_ratio < 0.3 or aspect_ratio > 3.0:
                score -= 0.2
                issues.append(f"Unusual aspect ratio ({aspect_ratio:.2f})")
            
            # Check for mostly white/blank content
            if image.mode != "L":
                gray = image.convert("L")
            else:
                gray = image
            
            # Calculate non-white pixel ratio
            img_array = np.array(gray)
            non_white = np.sum(img_array < 240) / img_array.size
            
            if non_white < self.THRESHOLDS["min_content_ratio"]:
                score -= 0.3
                issues.append("Image appears mostly blank")
            
            # Check edges for cutoff content
            edge_content = self._check_edge_content(gray)
            if edge_content:
                score -= 0.1
                issues.append("Content may be cut off at edges")
            
            return max(0, min(1, score)), issues
            
        except Exception as e:
            logger.warning(f"Completeness analysis failed: {e}")
            return 0.5, []
    
    def _check_edge_content(self, gray: Image.Image) -> bool:
        """Check if there's significant content at image edges."""
        try:
            img_array = np.array(gray)
            
            # Check edge strips (5 pixel wide)
            edge_width = 5
            
            # Get edge regions
            top = img_array[:edge_width, :].mean()
            bottom = img_array[-edge_width:, :].mean()
            left = img_array[:, :edge_width].mean()
            right = img_array[:, -edge_width:].mean()
            
            # If edges are significantly darker than white (< 200), 
            # content might be cut off
            threshold = 200
            edges_with_content = sum([
                top < threshold,
                bottom < threshold,
                left < threshold,
                right < threshold,
            ])
            
            return edges_with_content >= 2
            
        except Exception:
            return False
    
    def _collect_metrics(
        self,
        image: Image.Image,
        gray: Image.Image,
    ) -> Dict:
        """Collect raw metrics for debugging/analysis."""
        try:
            stat = ImageStat.Stat(gray)
            
            return {
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "mean_brightness": stat.mean[0],
                "std_dev": stat.stddev[0],
                "min_value": stat.extrema[0][0],
                "max_value": stat.extrema[0][1],
            }
        except Exception:
            return {}
    
    def _generate_recommendations(
        self,
        report: QualityReport,
    ) -> List[str]:
        """Generate improvement recommendations based on scores."""
        recommendations = []
        
        if report.sharpness_score < 0.6:
            recommendations.append("Consider re-extracting with higher resolution source")
        
        if report.brightness_score < 0.6:
            if "too dark" in str(report.issues):
                recommendations.append("Increase image brightness")
            else:
                recommendations.append("Reduce image brightness/exposure")
        
        if report.contrast_score < 0.6:
            recommendations.append("Enhance image contrast")
        
        if report.completeness_score < 0.7:
            recommendations.append("Verify bounding box captures complete product")
        
        return recommendations


def score_product_image(image: Image.Image) -> Tuple[float, bool, List[str]]:
    """
    Convenience function to score a product image.
    
    Args:
        image: PIL Image to score
        
    Returns:
        Tuple of (score, is_acceptable, issues)
    """
    scorer = QualityScorer()
    report = scorer.analyze(image)
    return report.overall_score, report.is_acceptable, report.issues